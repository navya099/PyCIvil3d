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
```

## 첫 구현 범위

- Civil 3D 2026 문서 기준으로 `TinSurface.Create(Database, String)`,
  `AddVertices(Point3dCollection)`, `FindElevationAtXY(Double, Double)`의
  인자와 반환 타입을 구현했습니다. `Database.get_object`는 독립 실행용 객체
  조회 메서드이며, `Database`는 메모리에 객체를 보관합니다.
- 브레이크라인과 사용자 정의 경계가 없는 Delaunay TIN을 지원합니다. 삼각망
  밖의 좌표나 면적을 가진 삼각형이 없는 표면을 조회하면
  `PointNotOnEntityException`을 발생시킵니다. 같은 XYZ는 한 번만 반영하며,
  같은 XY에 서로 다른 Z를 넣는 요청은 배치 전체를 거부합니다.
- 각 정점 배치에서 삼각망과 XY 경계 상자 트리를 다시 구성합니다. 표고
  조회는 해당 XY를 포함하는 경계 상자만 탐색합니다.
- Civil 3D 본체와의 수치 비교는 미검증 상태입니다. 지원 범위 밖에는 DWG,
  스타일, 트랜잭션, 표면 작업 편집, 세 메서드의 기타 오버로드가 포함됩니다.

API 문서는 [TinSurface](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/78a4066b-630e-0308-8393-fa77adeffa33.htm),
[AddVertices](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/a36eef1e-e3b4-24ff-0f04-a156b56d79fa.htm),
[FindElevationAtXY](https://help.autodesk.com/cloudhelp/2026/ENU/Civil3D-API/files/html/d280ff4f-4c4b-f910-7a27-0e787a43448f.htm)를 참고하세요.

삼각분할은 [delaunator-cpp](https://github.com/delfrrr/delaunator-cpp/tree/c1521f6e879881232dcddabd6c2ddb6187e8714b)
헤더를 사용합니다. 관련 라이선스는 `cpp/vendor`에 있습니다.

## 테스트

```sh
python -m unittest discover -s tests -v
```
