"""PostgreSQL pgvector UserDefinedType for vector embeddings (docs/03 §3.2, docs/04 §9)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.types import UserDefinedType


class PGVector(UserDefinedType):
    """pgvector column type supporting cosine distance (<=>), L2 distance (<->), and inner product (<#>)."""

    cache_ok = True

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dim})"

    def bind_processor(self, dialect: Any) -> Any:
        def process(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return "[" + ",".join(str(float(x)) for x in value) + "]"
            return str(value)

        return process

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        def process(value: Any) -> list[float] | None:
            if value is None:
                return None
            if isinstance(value, str):
                cleaned = value.strip("[] \t\r\n")
                if not cleaned:
                    return []
                return [float(x) for x in cleaned.split(",")]
            if isinstance(value, (list, tuple)):
                return [float(x) for x in value]
            return value

        return process

    class comparator_factory(UserDefinedType.Comparator):  # noqa: N801
        """Vector operator comparator for pgvector cosine distance and similarity."""

        def cosine_distance(self, other: Any) -> Any:
            """Cosine distance operator (<=>)."""
            return self.op("<=>")(other)

        def l2_distance(self, other: Any) -> Any:
            """L2 euclidean distance operator (<->)."""
            return self.op("<->")(other)

        def max_inner_product(self, other: Any) -> Any:
            """Negative inner product operator (<#>)."""
            return self.op("<#>")(other)
