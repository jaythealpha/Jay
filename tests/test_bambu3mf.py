"""trimesh 없이 Bambu 멀티컬러 3MF 구조 검증."""

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from bambu_auto.services.mesh.bambu3mf import write_bambu_multicolor_3mf


class FakeMesh:
    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces


def _cube():
    v = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
         (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    f = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
         (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
         (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return FakeMesh(v, f)


def test_writes_valid_3mf_zip(tmp_path: Path) -> None:
    parts = [_cube(), _cube(), _cube()]
    out = tmp_path / "m.bambu.3mf"
    write_bambu_multicolor_3mf(parts, out)

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "3D/3dmodel.model" in names
        assert "Metadata/model_settings.config" in names
        model = z.read("3D/3dmodel.model").decode()
        settings = z.read("Metadata/model_settings.config").decode()

    # 3dmodel.model 은 잘 형성된 XML 이고 파트3 + 조립1 = 오브젝트 4개
    ET.fromstring(model)
    assert model.count("<object ") == 4
    assert model.count("<component ") == 3

    # model_settings: 파트별 extruder 1,2,3 배정
    ET.fromstring(settings)
    for ext in (1, 2, 3):
        assert 'key="extruder" value="%d"' % ext in settings


def test_single_part(tmp_path: Path) -> None:
    out = tmp_path / "s.bambu.3mf"
    write_bambu_multicolor_3mf([_cube()], out)
    with zipfile.ZipFile(out) as z:
        model = z.read("3D/3dmodel.model").decode()
    ET.fromstring(model)
    assert model.count("<object ") == 2  # 파트1 + 조립1
