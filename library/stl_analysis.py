import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StlAnalysis:
    triangle_count: int
    file_size: int
    dimension_x: float
    dimension_y: float
    dimension_z: float
    volume_cm3: float | None
    file_type: str

    def as_dict(self) -> dict:
        return {
            "triangle_count": self.triangle_count,
            "file_size": self.file_size,
            "dimension_x": round(self.dimension_x, 2),
            "dimension_y": round(self.dimension_y, 2),
            "dimension_z": round(self.dimension_z, 2),
            "volume_cm3": round(self.volume_cm3, 2) if self.volume_cm3 is not None else None,
            "file_type": self.file_type,
        }


def analyze_stl_file(path: str | Path) -> StlAnalysis:
    path = Path(path)
    data = path.read_bytes()
    file_size = len(data)
    if file_size < 84:
        raise ValueError("File too small to be a valid STL")

    if _is_ascii_stl(data):
        return _analyze_ascii(data, file_size)

    return _analyze_binary(data, file_size)


def _is_ascii_stl(data: bytes) -> bool:
    header = data[:4096].lstrip()
    return header.lower().startswith(b"solid")


def _analyze_binary(data: bytes, file_size: int) -> StlAnalysis:
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + triangle_count * 50
    if expected > file_size:
        raise ValueError("Invalid binary STL: unexpected file size")

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    volume = 0.0
    offset = 84

    for _ in range(triangle_count):
        # normal (3 floats) + vertices (9 floats) + attribute (2 bytes)
        values = struct.unpack_from("<12f", data, offset)
        offset += 48
        offset += 2  # attribute byte count

        verts = [
            (values[3], values[4], values[5]),
            (values[6], values[7], values[8]),
            (values[9], values[10], values[11]),
        ]
        for x, y, z in verts:
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            min_z, max_z = min(min_z, z), max(max_z, z)

        volume += _signed_tetra_volume(verts[0], verts[1], verts[2])

    volume_cm3 = abs(volume) / 1000.0  # mm³ → cm³

    return StlAnalysis(
        triangle_count=triangle_count,
        file_size=file_size,
        dimension_x=max_x - min_x,
        dimension_y=max_y - min_y,
        dimension_z=max_z - min_z,
        volume_cm3=volume_cm3,
        file_type="stl",
    )


def _analyze_ascii(data: bytes, file_size: int) -> StlAnalysis:
    text = data.decode("utf-8", errors="ignore")
    triangle_count = text.lower().count("facet normal")
    verts = []
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    volume = 0.0

    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("vertex"):
            parts = line.split()
            if len(parts) >= 4:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                verts.append((x, y, z))
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                min_z, max_z = min(min_z, z), max(max_z, z)
                if len(verts) == 3:
                    volume += _signed_tetra_volume(verts[0], verts[1], verts[2])
                    verts = []

    return StlAnalysis(
        triangle_count=triangle_count,
        file_size=file_size,
        dimension_x=max_x - min_x if triangle_count else 0.0,
        dimension_y=max_y - min_y if triangle_count else 0.0,
        dimension_z=max_z - min_z if triangle_count else 0.0,
        volume_cm3=abs(volume) / 1000.0 if triangle_count else None,
        file_type="stl",
    )


def _signed_tetra_volume(p1: tuple[float, float, float], p2: tuple[float, float, float], p3: tuple[float, float, float]) -> float:
    return (
        -p3[0] * p2[1] * p1[2]
        + p2[0] * p3[1] * p1[2]
        + p3[0] * p1[1] * p2[2]
        - p1[0] * p3[1] * p2[2]
        - p2[0] * p1[1] * p3[2]
        + p1[0] * p2[1] * p3[2]
    )
