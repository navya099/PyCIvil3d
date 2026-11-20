using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil;
using Autodesk.Civil.DatabaseServices;
using Application = Autodesk.AutoCAD.ApplicationServices.Core.Application;
using Exception = System.Exception;

[assembly: CommandClass(typeof(Pycivil3d.TinReferenceExporter))]

namespace Pycivil3d;

public sealed class TinReferenceExporter
{
    [CommandMethod("PYCIVIL3D_EXPORT_TIN")]
    public void ExportTin()
    {
        var document = Application.DocumentManager.MdiActiveDocument;
        var editor = document.Editor;
        var input = editor.GetFileNameForOpen(
            new PromptOpenFileOptions("\nSelect a TIN input JSON file") { Filter = "JSON (*.json)|*.json" });
        if (input.Status != PromptStatus.OK)
            return;

        var output = editor.GetFileNameForSave(
            new PromptSaveFileOptions("\nChoose a new reference JSON file") { Filter = "JSON (*.json)|*.json" });
        if (output.Status != PromptStatus.OK)
            return;

        try
        {
            if (File.Exists(output.StringResult))
                throw new IOException("Choose a new output file. Existing files cannot be replaced.");

            using var json = JsonDocument.Parse(File.ReadAllText(input.StringResult));
            var points = json.RootElement.GetProperty("points").EnumerateArray()
                .Select(point => ReadCoordinates(point, 3)).ToArray();
            var queries = json.RootElement.GetProperty("queries").EnumerateArray()
                .Select(query => ReadCoordinates(query.GetProperty("xy"), 2)).ToArray();

            var (triangles, queryResults) = Capture(document.Database, points, queries);
            var reference = new
            {
                source = $"Autodesk Civil 3D / AeccDbMgd {typeof(TinSurface).Assembly.GetName().Version}",
                points,
                triangles,
                queries = queryResults
            };
            var bytes = JsonSerializer.SerializeToUtf8Bytes(reference, new JsonSerializerOptions { WriteIndented = true });
            SaveNewFile(output.StringResult, bytes);
            editor.WriteMessage($"\nReference saved to {output.StringResult}");
        }
        catch (Exception error)
        {
            editor.WriteMessage($"\nTIN reference export failed: {error.Message}");
        }
    }

    private static (List<double[][]> Triangles, List<QueryResult> Queries) Capture(
        Database database, double[][] points, double[][] queries)
    {
        var triangles = new List<double[][]>();
        var queryResults = new List<QueryResult>();
        // Disposing without commit rolls back the temporary surface.
        using var transaction = database.TransactionManager.StartTransaction();
        var id = TinSurface.Create(database, $"Pycivil3d reference {Guid.NewGuid():N}");
        var surface = (TinSurface)transaction.GetObject(id, OpenMode.ForWrite);
        using var locations = new Point3dCollection();
        foreach (var point in points)
            locations.Add(new Point3d(point[0], point[1], point[2]));

        if (locations.Count != 0)
            surface.AddVertices(locations).Dispose();
        surface.Rebuild();

        using (var mesh = surface.GetTriangles(false))
        {
            foreach (var triangle in mesh)
            {
                using var face = triangle;
                triangles.Add(TriangleLocations(face));
            }
        }

        foreach (var xy in queries)
        {
            double? elevation;
            try
            {
                elevation = surface.FindElevationAtXY(xy[0], xy[1]);
            }
            catch (PointNotOnEntityException)
            {
                elevation = null;
            }
            double[][]? triangle;
            try
            {
                using var face = surface.FindTriangleAtXY(xy[0], xy[1]);
                triangle = TriangleLocations(face);
            }
            catch (System.ArgumentException)
            {
                triangle = null;
            }

            queryResults.Add(new QueryResult(xy, elevation, triangle));
        }
        return (triangles, queryResults);
    }

    private static double[] ReadCoordinates(JsonElement element, int count)
    {
        if (element.ValueKind != JsonValueKind.Array || element.GetArrayLength() != count)
            throw new JsonException($"Expected an array of {count} coordinates.");

        var coordinates = element.EnumerateArray().Select(value => value.GetDouble()).ToArray();
        if (coordinates.Any(value => !double.IsFinite(value)))
            throw new JsonException("Coordinates must be finite.");
        return coordinates;
    }

    private static double[][] TriangleLocations(TinSurfaceTriangle triangle)
    {
        using var first = triangle.Vertex1;
        using var second = triangle.Vertex2;
        using var third = triangle.Vertex3;
        return [ToArray(first.Location), ToArray(second.Location), ToArray(third.Location)];
    }

    private static double[] ToArray(Point3d point) => [point.X, point.Y, point.Z];

    private static void SaveNewFile(string path, byte[] bytes)
    {
        var temporary = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path))!, $".pycivil3d-{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllBytes(temporary, bytes);
            File.Move(temporary, path);
        }
        finally
        {
            File.Delete(temporary);
        }
    }

    private sealed record QueryResult(double[] xy, double? elevation, double[][]? triangle);
}
