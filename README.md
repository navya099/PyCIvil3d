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
  두 조회 메서드가 표면별로 기억하는 마지막 삼각형이 해당 XY를 포함하면
  우선 선택합니다. 그 외에는 Pycivil3d의 삼각망 순서에서 먼저 나타나는
  삼각형을 선택합니다. 표면을 다시 구성하면 이전 선택을 초기화합니다.
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

### 좌표별 삼각형 선택 비교

저장소를 업데이트한 뒤 기존 가상환경을 사용 중이면, 저장소 루트에서
C++ 확장을 다시 빌드하세요. Python 소스와 C++ 확장은 함께 업데이트해야 합니다.

```powershell
python -m pip install --no-cache-dir --force-reinstall -e .
```

최신 내보내기 명령은 각 조회에 `FindTriangleAtXY`로 찾은 삼각형의 정점
XYZ를 `triangle`로 기록합니다. 삼각형을 찾을 수 없으면 `null`을 기록합니다.
비교 도구는 정점 순서를 무시하고 해당 삼각형의 XYZ를 정확히 비교합니다.
`triangle` 필드가 없는 기존 파일은 삼각망과 표고만 비교합니다.

공유 모서리와 정점의 선택을 검증하려면 플러그인을 다시 빌드해 로드하고
위의 네 점 입력 두 개를 새 JSON 파일로 다시 내보냅니다. 두 입력 모두
중앙 `(5, 5)`가 공유 모서리 위에 있고 `(10, 10)`은 TIN 정점입니다.

### 로드된 빌드 확인

Civil 3D에서 최신 `TinReferenceExporter.dll`을 `NETLOAD`로 로드하면
명령창에 DLL 버전과 모듈 식별자(MVID)가 표시됩니다. 같은 정보가 출력
JSON의 `exporterBuild`에도 기록됩니다. 새 DLL로 교체해 확인할 때는
Civil 3D를 다시 시작한 뒤 새 DLL을 로드하세요.

Python이 로드한 C++ 확장의 버전, 컴파일 시각, 파일 경로는 활성
가상환경에서 다음 명령으로 확인할 수 있습니다.

```powershell
python -c "import pycivil3d._core as c; print(c.__version__, c.__build_stamp__, c.__file__)"
```

### 여러 공유 모서리 비교

`tests/fixtures/civil3d_inputs/tin_shared_edges.json`은 내부 정점
`(4, 5)`를 포함하는 네 삼각형을 대상으로 합니다. 첫 12개 조회는
내부 모서리 네 개의 중점과 각 중점에서 X를 ±0.125 이동한 좌표입니다.
나머지 세 조회는 내부 정점, 외곽 정점, 표면 밖 좌표입니다.

Civil 3D에서 `PYCIVIL3D_EXPORT_TIN`으로 이 입력을 열고
`shared-edges-reference.json`으로 저장한 뒤 비교합니다.

```powershell
python tools/compare_tin.py shared-edges-reference.json --abs-tol 1e-8
```

같은 방향 선택이 유지되는지 확인하려면 다음 두 입력도 같은 방법으로
내보냅니다. 세 입력의 조회 순서는 같으므로 출력의 같은 인덱스를 대조할
수 있습니다.

- `tin_shared_edges_rotated.json`은 점과 조회 좌표를 원점 기준으로
  반시계 방향 90도 회전했습니다. 출력 정점을 `(x, y) → (y, -x)`로
  되돌리면 원본과 같은 위치에서 선택한 삼각형을 비교할 수 있습니다.
- `tin_shared_edges_reordered.json`은 점과 조회 좌표가 같고, 내부 정점을
  첫 번째로 옮기는 등 정점 입력 순서만 바꿨습니다.

### 두 내부 정점 사이의 모서리 비교

`tests/fixtures/civil3d_inputs/tin_interior_edge.json`은 원래 공유 모서리
입력에 내부 정점 `(8, 4)`를 추가합니다. 첫 아홉 조회는 `(4, 5)`에서
`(8, 4)`로 이어지는 모서리 위의 25%, 50%, 75% 지점과, 각 지점의 Y를
−0.125 및 +0.125 이동한 좌표입니다. 마지막 세 조회는 양 끝 정점과
표면 밖 좌표입니다.

Civil 3D에서 `PYCIVIL3D_EXPORT_TIN`으로 이 입력을 실행해 새 JSON으로
저장하고 비교합니다.

```powershell
python tools/compare_tin.py interior-edge-reference.json --abs-tol 1e-8
```

`tests/fixtures/civil3d_inputs/tin_interior_edge_sweep.json`은 같은 점을
사용하고, 공유 모서리 내부의 15개 좌표를 1/16 간격으로 조회합니다.
앞 15개 조회는 `(4, 5)` 쪽에서 `(8, 4)` 쪽으로 진행하고, 뒤 15개는
같은 좌표를 역순으로 조회합니다. 출력에서 같은 XY의 두 `triangle` 값을
대조하면 조회 순서에 따른 차이를 확인할 수 있습니다. 끝 정점은 별도
정점 선택의 영향을 피하기 위해 이 입력에서 제외했습니다.

`tests/fixtures/civil3d_inputs/tin_interior_edge_query_order.json`은 모서리
중점 `(6, 4.5)`을 위쪽 `(6, 4.625)`과 아래쪽 `(6, 4.375)` 조회 직후에
번갈아 조회합니다. 처음 두 순서에서는 중점을 한 번 더 조회해 결과가
유지되는지도 확인합니다. 출력의 `queries` 순서와 중복 좌표를 유지해야
직전 조회의 영향을 비교할 수 있습니다. 기존 내보내기 명령은 각 좌표에서
`FindElevationAtXY`를 호출한 뒤 `FindTriangleAtXY`를 호출하므로,
이 입력은 두 호출을 포함한 조회 순서의 영향을 검사합니다.

`tin_interior_edge_lookup_methods.json`은 두 조회 메서드의 영향을 따로
확인하는 입력입니다. 최신 DLL을 다시 빌드해 로드한 뒤 내보냅니다.
입력의 `lookup`이 `triangle` 또는 `elevation`이면 해당 메서드만
호출하며, 생략하거나 `both`이면 표고와 삼각형을 순서대로 호출합니다.
출력에는 호출한 메서드의 결과 필드만 기록됩니다. 결과가 `null`이면
해당 메서드를 호출했지만 좌표에 대응하는 결과가 없었다는 의미입니다.

2번과 4번 조회는 각각 위쪽과 아래쪽에서 삼각형만 조회한 직후의 중점
결과입니다. 7번과 10번은 반대편의 표고만 추가로 조회한 직후의 중점
결과입니다. 비교 도구도 출력에 기록된 호출만 순서대로 실행합니다.

Civil 3D 2026의 단독 호출 결과는
`tests/fixtures/civil3d_reference/tin_interior_edge_lookup_methods.json`에
보관하며 일반 테스트에서 비교합니다. 첫 조회부터 공유 모서리에 놓이는
경우와 이전 삼각형이 다음 공유 모서리를 포함하지 않는 경우의 Civil 3D
선택 규칙은 아직 확인되지 않았습니다.

### 이전 삼각형을 재사용할 수 없는 조회

아래 파일을 `PYCIVIL3D_EXPORT_TIN`으로 각각 내보냅니다. 명령을 실행할
때마다 별도 임시 표면을 만들며, 각 입력은 `FindTriangleAtXY`만 호출합니다.
기존 `lookup` 옵션을 지원하는 DLL로 실행할 수 있습니다.

- `tin_interior_edge_first_quarter.json`은 모서리의 25% 지점을 먼저 조회합니다.
- `tin_interior_edge_first_three_quarters.json`은 같은 모서리의 75% 지점을
  먼저 조회합니다. 두 출력의 첫 삼각형을 대조하면 이전 조회 없이 모서리
  위 위치에 따라 결과가 달라지는지 확인할 수 있습니다.
- `tin_interior_edge_after_unrelated.json`은 모서리에 인접하지 않은 서로
  다른 두 삼각형을 조회한 뒤, 각각 같은 모서리 중점 `(6, 4.5)`을 조회합니다.
  출력의 두 번째와 네 번째 삼각형이 비교 대상입니다.

`tin_interior_edge_after_interior_queries.json`은 앞선 입력의 선행 조회를
보완합니다. 선행 좌표 `(1, 6)`, `(10, 1)`, `(10, 5)`는 각각
목표 모서리를 포함하지 않는 서로 다른 삼각형의 내부에 있습니다.
`PYCIVIL3D_EXPORT_TIN`으로 이 입력을 내보내고, 두 번째·네 번째·여섯 번째
조회가 같은 중점 `(6, 4.5)`에서 반환한 삼각형을 대조합니다.

`tin_interior_edge_multistep.json`은 기존 점에 외곽 점 네 개를 추가합니다.
각 홀수 번째 조회는 삼각형 내부에 있고, 그 직후에는 모서리 중점
`(6, 4.5)`을 조회합니다. 변을 공유하는 삼각형끼리 이동한다고 가정하면,
Pycivil3d의 삼각망에서 선행 삼각형마다 중점 양쪽까지의 최단 이동 횟수는
다음과 같습니다.

| 선행 좌표 | 위쪽 삼각형 | 아래쪽 삼각형 |
| --- | ---: | ---: |
| `(12.25, 18.25)` | 3 | 4 |
| `(8.75, -9)` | 4 | 3 |
| `(-6.75, 7.25)` | 3 | 3 |
| `(22, 6.75)` | 3 | 3 |

기존 DLL의 `PYCIVIL3D_EXPORT_TIN`으로 내보낸 뒤 먼저 전체 삼각망이
일치하는지 확인합니다. 이어서 짝수 번째 조회를 대조하면, 최단 이동
횟수가 다른 경우와 같은 경우의 선택을 각각 확인할 수 있습니다.
