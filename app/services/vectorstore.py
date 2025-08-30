from __future__ import annotations
import logging
from typing import List, Dict
from app.config import get_settings

log = logging.getLogger("vectorstore")

def _cosine(a: List[float], b: List[float]) -> float:
    dot = 0.0; na = 0.0; nb = 0.0
    for x, y in zip(a, b):
        dot += x*y; na += x*x; nb += y*y
    if na == 0 or nb == 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))

class VectorStore:
    def __init__(self):
        self.settings = get_settings()
        self.use_pg: bool = False
        self._mem: Dict[str, List[Dict]] = {}
        dsn = self.settings.pg_dsn
        if dsn:
            try:
                try:
                    import psycopg
                    self._pg = ("psycopg3", psycopg)
                except Exception:
                    import psycopg2
                    self._pg = ("psycopg2", psycopg2)
                self._conn = self._connect()
                self.use_pg = True
                log.info("vectorstore: PG enabled")
            except Exception as e:
                log.warning("vectorstore: PG connect failed, falling back to memory: %s", e)
        else:
            log.info("vectorstore: PG not configured; using in-memory store")

    # ---------- public API ----------

    def upsert(self, namespace: str, url: str, content: str, vector: List[float]) -> None:
        if self.use_pg:
            self._pg_upsert(namespace, url, content, vector)
        else:
            self._mem.setdefault(namespace, []).append({"url": url, "content": content, "vector": vector})

    def search(self, namespace: str, query_vec: List[float], top_k: int = 5) -> List[Dict]:
        if self.use_pg:
            return self._pg_search(namespace, query_vec, top_k)
        items = self._mem.get(namespace, [])
        rows = [{"url": it["url"], "text": it["content"], "score": float(_cosine(query_vec, it["vector"]))} for it in items]
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows[:top_k]

    def clear_namespace(self, namespace: str) -> int:
        """Delete all vectors under a namespace. Returns deleted row count."""
        if self.use_pg:
            schema = self.settings.pg_schema; table = self.settings.pg_table
            sql = f"DELETE FROM {schema}.{table} WHERE namespace = %s"
            with self._conn.cursor() as cur:
                cur.execute(sql, (namespace,))
                return cur.rowcount or 0
        n = len(self._mem.get(namespace, []))
        self._mem.pop(namespace, None)
        return n

    # ---------- PG helpers ----------
    def _connect(self):
        dsn = self.settings.pg_dsn
        if self._pg[0] == "psycopg3":
            psycopg = self._pg[1]; return psycopg.connect(dsn, autocommit=True)
        psycopg2 = self._pg[1]; conn = psycopg2.connect(dsn); conn.autocommit = True; return conn

    def _ensure_extension_and_table(self, dim: int):
        schema = self.settings.pg_schema; table = self.settings.pg_table
        dist = (self.settings.pg_distance or "cosine").lower()
        ops = {"cosine": "vector_cosine_ops","l2":"vector_l2_ops","ip":"vector_ip_ops"}.get(dist, "vector_cosine_ops")
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE SCHEMA IF NOT EXISTS {schema};
        CREATE TABLE IF NOT EXISTS {schema}.{table}(
            id BIGSERIAL PRIMARY KEY,
            namespace TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT,
            embedding VECTOR({dim}),
            UNIQUE(namespace, url)
        );
        CREATE INDEX IF NOT EXISTS {table}_ns_idx ON {schema}.{table}(namespace);
        """
        with self._conn.cursor() as cur:
            cur.execute(ddl)

    def _pg_upsert(self, namespace: str, url: str, content: str, vector: List[float]) -> None:
        self._ensure_extension_and_table(len(vector))
        schema = self.settings.pg_schema; table = self.settings.pg_table
        vec = "[" + ",".join(f"{x:.7f}" for x in vector) + "]"
        sql = f"""
        INSERT INTO {schema}.{table}(namespace,url,content,embedding)
        VALUES(%s,%s,%s,%s::vector)
        ON CONFLICT(namespace,url) DO UPDATE SET content=EXCLUDED.content, embedding=EXCLUDED.embedding;
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (namespace, url, content, vec))

    def _pg_search(self, namespace: str, query_vec: List[float], top_k: int) -> List[Dict]:
        schema = self.settings.pg_schema; table = self.settings.pg_table
        vec = "[" + ",".join(f"{x:.7f}" for x in query_vec) + "]"
        sql = f"""
        SELECT url, content, 1 - (embedding <=> %s::vector) AS score
        FROM {schema}.{table}
        WHERE namespace=%s
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (vec, namespace, vec, top_k))
            rows = cur.fetchall()
        return [{"url": u, "text": c, "score": float(s)} for (u, c, s) in rows]
