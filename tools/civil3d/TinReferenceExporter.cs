using System.Reflection;
using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil;
using Autodesk.Civil.DatabaseServices;
using Application = Autodesk.AutoCAD.ApplicationServices.Core.Application;
using Exception = System.Exception;

[assembly: ExtensionApplication(typeof(Pycivil3d.TinReferenceExporter))]
[assembly: CommandClass(typeof(Pycivil3d.TinReferenceExporter))]

namespace Pycivil3d;

public sealed class TinReferenceExporter : IExtensionApplication
{
    private static string ExporterBuild
    {
        get
        {
            var assembly = typeof(TinReferenceExporter).Assembly;
            var version = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()
                ?.InformationalVersion ?? assembly.GetName().Version?.ToString();
            return $"{version} (MVID {assembly.ManifestModule.ModuleVersionId})";
        }
    }

    public void Initialize()
    {
        Application.DocumentManager.MdiActiveDocument?.Editor.WriteMessage(
            $"\nPycivil3d TIN reference exporter loaded: {ExporterBuild}");
    }

    public void Terminate() { }

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
                .Select(ReadQuery).ToArray();

            var (triangles, queryResults) = Capture(document.Database, points, queries);
            var reference = new
            {
                source = $"Autodesk Civil 3D / AeccDbMgd {typeof(TinSurface).Assembly.GetName().Version}",
                exporterBuild = ExporterBuild,
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

    private static (List<double[][]> Triangles, List<Dictionary<string, object?>> Queries) Capture(
        Database database, double[][] points, Query[] queries)
    {
        var triangles = new List<double[][]>();
        var queryResults = new List<Dictionary<string, object?>>();
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

        foreach (var query in queries)
        {
            var xy = query.Xy;
            var result = new Dictionary<string, object?> { ["xy"] = xy };
            if (query.Lookup is "both" or "elevation")
            {
                try
                {
                    result["elevation"] = surface.FindElevationAtXY(xy[0], xy[1]);
                }
                catch (PointNotOnEntityException)
                {
                    result["elevation"] = null;
                }
            }

            if (query.Lookup is "both" or "triangle")
            {
                try
                {
                    using var face = surface.FindTriangleAtXY(xy[0], xy[1]);
                    result["triangle"] = TriangleLocations(face);
                }
                catch (System.ArgumentException)
                {
                    result["triangle"] = null;
                }
            }
            queryResults.Add(result);
        }
        return (triangles, queryResults);
    }

    private static Query ReadQuery(JsonElement query)
    {
        var xy = ReadCoordinates(query.GetProperty("xy"), 2);
        var lookup = query.TryGetProperty("lookup", out var mode) ? mode.GetString() : "both";
        if (lookup is not ("both" or "elevation" or "triangle"))
            throw new JsonException("lookup must be both, elevation, or triangle.");
        return new Query(xy, lookup);
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

    private sealed record Query(double[] Xy, string Lookup);
}
