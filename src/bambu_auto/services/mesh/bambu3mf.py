"""Bambu / Orca Studio 호환 멀티컬러 3MF 작성기.

trimesh 기본 3MF는 '필라멘트(익스트루더) 배정'을 담지 못해 Bambu Studio에서
단색으로 보인다. 색을 자동 배정하려면 각 색 영역을 별도 '파트'로 나누고
파트마다 extruder 번호를 지정해야 한다.

여기서는 표준 3MF 조립(<components>)으로 파트들을 한 오브젝트로 묶고,
Metadata/model_settings.config 에 파트별 extruder 를 적어 'model 3MF'로
내보낸다. 이 형식은 Bambu Studio가 import 시 각 파트를 익스트루더 1..N에
배정하므로, AMS에 팔레트 색을 끼우면 그대로 다색 출력된다.

project_settings.config(전체 슬라이싱 프로파일)는 일부러 넣지 않는다 —
불완전한 프로파일은 Bambu Studio가 거부할 수 있고, '모델 import'가 더
견고하기 때문. 대신 동봉 palette.json 으로 어떤 색이 몇 번 익스트루더인지
알 수 있다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    "</Types>"
)

_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    "</Relationships>"
)

_IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"
_PART_MATRIX = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


def _mesh_object_xml(obj_id: int, mesh) -> str:
    """단일 메쉬를 <object type='model'> XML로 (vertices+triangles)."""
    v = mesh.vertices
    f = mesh.faces
    rows = ["".join((
        '<vertex x="%.5f" y="%.5f" z="%.5f"/>' % (p[0], p[1], p[2])
    ) for p in v)]
    tris = ["".join((
        '<triangle v1="%d" v2="%d" v3="%d"/>' % (t[0], t[1], t[2])
    ) for t in f)]
    return (
        '<object id="%d" type="model">' % obj_id
        + "<mesh><vertices>" + "".join(rows) + "</vertices>"
        + "<triangles>" + "".join(tris) + "</triangles></mesh></object>"
    )


def _model_xml(parts) -> tuple[str, int]:
    """parts: list[mesh]. 각 파트를 오브젝트로, components로 한 조립 오브젝트.
    반환 (xml, assembly_id)."""
    n = len(parts)
    assembly_id = n + 1
    objs = [_mesh_object_xml(i + 1, m) for i, m in enumerate(parts)]
    comps = "".join(
        '<component objectid="%d" transform="%s"/>' % (i + 1, _IDENTITY)
        for i in range(n)
    )
    assembly = (
        '<object id="%d" type="model"><components>%s</components></object>'
        % (assembly_id, comps)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
        '<metadata name="Application">BambuAuto</metadata>'
        "<resources>" + "".join(objs) + assembly + "</resources>"
        '<build><item objectid="%d" transform="%s"/></build>'
        "</model>"
    ) % (assembly_id, _IDENTITY)
    return xml, assembly_id


def _model_settings_xml(parts, assembly_id: int) -> str:
    """파트별 extruder(=색 순서) 배정. extruder는 1부터."""
    part_xml = []
    for i in range(len(parts)):
        ext = i + 1
        part_xml.append(
            '<part id="%d" subtype="normal_part">' % (i + 1)
            + '<metadata key="name" value="color_%d"/>' % ext
            + '<metadata key="matrix" value="%s"/>' % _PART_MATRIX
            + '<metadata key="extruder" value="%d"/>' % ext
            + "</part>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<config>"
        '<object id="%d">' % assembly_id
        + '<metadata key="name" value="multicolor"/>'
        + '<metadata key="extruder" value="1"/>'
        + "".join(part_xml)
        + "</object></config>"
    )


def write_bambu_multicolor_3mf(parts, out_path: Path) -> Path:
    """parts: list[trimesh.Trimesh] (색 순서 = 익스트루더 1..N).
    Bambu/Orca가 파트별 익스트루더로 읽는 model 3MF를 작성."""
    model_xml, assembly_id = _model_xml(parts)
    settings_xml = _model_settings_xml(parts, assembly_id)
    out_path = Path(out_path)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("3D/3dmodel.model", model_xml)
        z.writestr("Metadata/model_settings.config", settings_xml)
    return out_path
