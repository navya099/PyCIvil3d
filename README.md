# Pycivil3d

GUI 없이 Python에서 사용하는 토목 계산 라이브러리입니다. C++17 코어가 TIN
삼각분할과 표고 보간을 수행하며, Python 패키지가 Civil 3D의 공개 API를
기준으로 객체와 메서드를 제공합니다.

## 설치와 예제

Python 3.9 이상과 C++17 컴파일러가 필요합니다.

```sh
python -m pip install .
```

```python
from pycivil3d import Database, Point3d, Point3dCollection, TinSurface

database = Database()
surface_id = TinSurface.Create(database, "Existing Ground")
surface = database.get_object(surface_id)

points = Point3dCollection()
points.Add(Point3d(0, 0, 100))
points.Add(Point3d(10, 0, 110))
points.Add(Point3d(0, 10, 120))
operation = surface.AddVertices(points)

assert operation.Locations.Count == 3
assert surface.FindElevationAtXY(2, 3) == 108.0

triangle = surface.FindTriangleAtXY(2, 3)
assert triangle.Surface is surface

triangles = surface.GetTriangles(False)
assert triangles.Count == 1
for triangle in triangles:
    print([(p.X, p.Y, p.Z) for p in (
        triangle.Vertex1.Location, triangle.Vertex2.Location, triangle.Vertex3.Location,
    )])
```

## 지원 범위

- Civil 3D 2026 문서 기준으로 `TinSurface.Create(Database, String)`,
  `AddVertices(Point3dCollection)`, `FindElevationAtXY(Double, Double)`의
  인자와 반환 타입을 구현했습니다. `Database.get_object`는 독립 실행용 객체
  조회 메서드이며, `Database`는 메모리에 객체를 보관합니다.
- 브레이크라인과 사용자 정의 경계가 없는 Delaunay TIN을 지원합니다. 삼각망
  밖의 좌표나 면적을 가진 삼각형이 없는 표면을 조회하면
  `PointNotOnEntityException`을 발생시킵니다. 같은 XYZ는 한 번만 반영하며,
  같은 XY에 서로 다른 Z를 넣는 요청은 배치 전체를 거부합니다.
- `FindTriangleAtXY(x, y)`는 해당 XY를 포함하는 삼각형을 반환하며,
  삼각형을 찾을 수 없으면 `ValueError`를 발생시킵니다. 공유 모서리나 정점에서는
  Pycivil3d의 삼각망 순서에서 먼저 나타나는 삼각형을 선택합니다.
  [Civil 3D API](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/8b567439-3b5b-78ab-ead7-d1195eb79444.htm)
- `GetTriangles(includeInvisible)`와 `Triangles`는 조회 시점의 삼각망을
  반환합니다. 현재 사용자 정의 경계가 없어 모든 삼각형이 보이며, 두
  `includeInvisible` 값 모두 같은 삼각형 집합을 반환합니다.
- 각 정점 배치에서 삼각망과 XY 경계 상자 트리를 다시 구성합니다. 표고
  조회는 해당 XY를 포함하는 경계 상자만 탐색합니다.
- Civil 3D 본체와의 수치 비교는 미검증 상태입니다. 지원 범위 밖에는 DWG,
  스타일, 트랜잭션, 표면 작업 편집, 정점 추가와 표면 생성의 기타 오버로드가 포함됩니다.

API 문서는 [TinSurface](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/78a4066b-630e-0308-8393-fa77adeffa33.htm),
[AddVertices](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/a36eef1e-e3b4-24ff-0f04-a156b56d79fa.htm),
[FindElevationAtXY](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/d280ff4f-4c4b-f910-7a27-0e787a43448f.htm)를 참고하세요.

삼각분할은 [delaunator-cpp](https://github.com/delfrrr/delaunator-cpp/tree/c1521f6e879881232dcddabd6c2ddb6187e8714b)
헤더를 사용합니다. 관련 라이선스는 `cpp/vendor`에 있습니다.

## 테스트

```sh
python -m unittest discover -s tests -v
```

## Civil 3D 결과 비교

```sh
python tools/compare_tin.py tests/fixtures/tin_planar_manual.json
python tools/compare_tin.py civil3d-reference.json --abs-tol 1e-8
```

예제 파일의 기대값은 평면 방정식으로 계산했습니다. Civil 3D에서 기준 파일을
만들 때는 `points`의 입력 순서를 유지해 `AddVertices`를 한 번 호출합니다.
`GetTriangles(false)`의 각 삼각형은 세 정점의 XYZ 배열로 `triangles`에
기록합니다. 각 조회의 XY와 `FindElevationAtXY` 결과는 `queries`에 기록하고,
`PointNotOnEntityException`은 `elevation: null`로 기록합니다.

삼각형과 삼각형 내 정점의 열거 순서는 비교에서 무시합니다. 정점 XYZ는
정확히 비교하며, 표고에는 `--abs-tol`의 절대 허용오차를 적용합니다.
좌표와 표고는 기준 파일에 저장할 때 반올림 없이 내보내세요. 종료 코드는
일치 0, 결과 불일치 1, 입력 또는 실행 오류 2입니다.

### Civil 3D 2026에서 기준 JSON 만들기

Civil 3D와 해당 버전의 .NET SDK가 설치된 Windows에서 저장소를 연 뒤
PowerShell로 프로젝트를 빌드합니다.

```powershell
dotnet build tools/civil3d/TinReferenceExporter.csproj -c Release
```

기본 대상은 Civil 3D 2026~2026.2.1의 `net8.0-windows`입니다. Autodesk가
.NET 10을 지정한 2026.2.2 이후 버전은 빌드에
`-p:TargetFramework=net10.0-windows`를 추가합니다. 설치 위치가 다르면
`-p:Civil3DDir`에 AutoCAD 설치 폴더를 지정합니다. 필요하면
`-p:Civil3DAssemblyDir`과 `-p:AecAssemblyDir`로 각각
`AeccDbMgd.dll`과 `AecBaseMgd.dll`이 있는 폴더를 지정합니다.
[Autodesk .NET 및 어셈블리 안내](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-DevGuide/files/GUID-267E68C8-AD2D-4F7F-87DF-831018D56CDB.htm)

1. Civil 3D에서 새 도면을 열고 `NETLOAD`로 빌드된
   `TinReferenceExporter.dll`을 로드합니다.
2. `PYCIVIL3D_EXPORT_TIN`을 실행합니다. 첫 입력으로
   `tests/fixtures/tin_planar_manual.json`을 선택하고 새 출력 JSON 경로를
   지정합니다. 내보내기 명령은 입력의 정점과 조회 XY만 읽어 결과를 다시
   계산합니다. 임시 표면을 만든 트랜잭션은 커밋하지 않습니다.
3. 출력 파일을 `python tools/compare_tin.py <출력 파일>`에 전달합니다.

### 같은 원 위의 네 점 비교

`tests/fixtures/civil3d_inputs`의 `tin_cocircular_abcd.json`과
`tin_cocircular_bcda.json`은 동일한 정점과 조회 좌표를 사용합니다.
두 번째 파일은 첫 정점만 순환 이동해 시작점을 바꿉니다.

`PYCIVIL3D_EXPORT_TIN`으로 두 입력을 각각 실행해
`cocircular-abcd-reference.json`과 `cocircular-bcda-reference.json`으로
저장합니다. 그런 다음 두 출력 파일을 비교 도구에 전달합니다.

```powershell
python tools/compare_tin.py cocircular-abcd-reference.json cocircular-bcda-reference.json --abs-tol 1e-8
```

중앙 `(5, 5)`의 표고는 `(0, 0)`–`(10, 10)` 대각선이면 10이고,
`(10, 0)`–`(0, 10)` 대각선이면 0입니다. 비교 도구는 정점 순서에
관계없이 대각선 차이를 삼각망 불일치로 보고합니다.

Civil 3D 2026에서 내보낸 두 결과는 `tests/fixtures/civil3d_reference`에
보관합니다. 두 파일에 기록된 `AeccDbMgd` 버전은 `13.8.0.280`입니다.
일반 테스트 실행 시 이 결과를 기준으로 삼각망, 표고, 표면 밖 조회를 검사합니다.
