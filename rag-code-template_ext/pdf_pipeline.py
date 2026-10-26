"""사내 규정 PDF → 정제 → 청킹 → FAISS 적재 파이프라인.

/upload-paper 와 ingest.py 가 같은 함수를 사용한다.

청킹 방식은 환경변수 CHUNK_MODE 로 고른다.
- fixed   : 고정 크기 500자, 중첩 50자 (Day2 기본값)
- article : 조문(제N조) 단위, 긴 조문은 항(1. 2. 3.) 단위로 다시 나눔 (Day3 개선)
"""
import logging
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pdfplumber

BASE_DIR = Path(__file__).resolve().parent
PDF_STORE_PATH = BASE_DIR / "faiss_db" / "pdf"
# 평가셋 기준 ada-002 보다 검색이 좋아서 전환했다(fixed MRR 0.778 → 0.823). 바꾸면 차원이 달라지므로 ingest.py 로 다시 적재한다.
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")


def embeddings():
    return OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL", EMBEDDING_MODEL), request_timeout=30, max_retries=0)

CHUNK_MODE = os.getenv("CHUNK_MODE", "fixed")
FIXED_CHUNK_SIZE = 500
FIXED_CHUNK_OVERLAP = 50
ARTICLE_MAX_CHARS = 1000

# 줄 단위 구조 패턴
CHAPTER_RE = re.compile(r"^제\d+장\s+\S")
# "제12조 배우자 출산전후휴가", "제9조의2(연차)" 는 잡고
# "제13조·제14조를 적용한다", "제60조가 정한 …" 같은 본문 인용은 제외한다
ARTICLE_RE = re.compile(r"^(제\d+조(?:의\d+)?)(?:[ \t]+|\()([^()\n]{0,39}[^.()\s])\)?$")
SECTION_RE = re.compile(r"^(부칙|부록)\S*")
# 이 제목부터 문서 끝까지는 답변 근거가 아니므로 적재하지 않는다
DROP_FROM_RE = re.compile(r"^(법령\S*\s*확인\s*근거|부록\s*[A-Z]?\.?\s*확인 법령과 출처)")
CHECKLIST_RE = re.compile(r"^(\d+\.\s*)?☐")
LIST_ITEM_RE = re.compile(r"^(\d+\.|-|☐)\s")
# 규정 용어 → 직원이 실제로 쓰는 말. 조문 제목·본문에 규정 용어가 있으면 제목 줄에 관련어로 덧붙여
# "월급", "출산휴가"처럼 규정과 다른 말로 물어도 검색되게 한다(질의 표현 차이 대응).
# 평가셋 fixed 기준 MRR 0.823 → 0.833, 튜닝에 안 쓴 새 질문 12개 기준 0.715 → 0.767 (임베딩 3-large).
SYNONYMS = {
    "출산전후휴가": ["출산휴가"],
    "배우자 출산전후휴가": ["배우자 출산휴가", "남편 출산휴가"],
    "임금": ["월급", "급여"],
    "지급일": ["월급날"],
    "혼인": ["결혼"],
    "사망": ["상(喪)", "장례"],
    "경조금": ["부조금", "조의금", "축의금"],
    "경조휴가": ["결혼휴가", "상조휴가"],
    "노동절": ["근로자의 날"],
    "연장근로": ["야근", "초과근무"],
    "야간근로": ["밤샘 근무", "야간 근무"],
    "휴게": ["점심시간", "쉬는 시간"],
    "시업": ["출근 시간"],
    "종업": ["퇴근 시간"],
    "연차": ["연차휴가"],
    "여비": ["출장비"],
    "식대": ["밥값", "점심값"],
    "정년": ["은퇴 나이"],
    "수습": ["수습사원", "인턴 기간"],
    "감액": ["깎임"],
    "병가": ["아플 때 휴가"],
    "퇴직급여": ["퇴직금"],
    "괴롭힘": ["갑질"],
}
DOC_NO_RE = re.compile(r"SCT-[A-Z]+-\d{3}")
VERSION_RE = re.compile(r"(\d+\.\d+)\s*/\s*\S+")


@dataclass
class Section:
    """조문 또는 조문이 아닌 구획(문서 개요, 부칙, 부록) 하나."""
    chapter: str
    article: str  # "제12조" 또는 "" (조문이 아닌 구획)
    title: str
    page: int
    lines: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.article} {self.title}".strip()

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def label_with_aliases(self) -> str:
        """제목 줄 + 규정 용어의 일상어. 예: 제10조 출산전후휴가 (관련어: 출산휴가)"""
        body = f"{self.title}\n{self.text}"
        found = []
        for term, words in SYNONYMS.items():
            # 제목에 있거나 본문에 2번 이상 나오는 용어만. 한 번 스치듯 언급된 조문까지 붙이면 검색이 흐려진다.
            if term in self.title or self.text.count(term) >= 2:
                found += [w for w in words if w not in body and w not in found]
        return f"{self.label} (관련어: {', '.join(found)})" if found else self.label


@dataclass
class ParsedDoc:
    source: str
    doc: str
    doc_no: str
    version: str
    sections: list[Section]


# ---------------------------------------------------------------- 추출·정제

# 우리 PDF의 폰트 정보 경고(FontBBox)는 추출 결과와 무관해서 숨긴다.
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def extract_pages(file_path: str | Path) -> list[str]:
    """페이지별 텍스트. 표는 pdfplumber로 따로 읽어 원래 위치에 "행: 열 값" 문장으로 넣는다."""
    pages = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            parts, top = [], 0
            for table in sorted(page.find_tables(), key=lambda t: t.bbox[1]):
                parts.append(page.crop((0, top, page.width, table.bbox[1])).extract_text() or "")
                parts.append(table_to_text(table.extract()))
                top = table.bbox[3]
            parts.append(page.crop((0, top, page.width, page.height)).extract_text() or "")
            pages.append("\n".join(p for p in parts if p.strip()))
    return pages


def table_to_text(rows: list[list[str | None]]) -> str:
    """표를 행마다 한 줄로 바꾼다. 텍스트만 뽑으면 "일반 출산 90일 45일"처럼 어느 칸 값인지 사라지기 때문이다.

    2열 표:  - 문서번호: SCT-HR-004
    3열 이상: - 일반 출산: 총 기간, 역일 90일; 출산 후 최소 확보기간 45일
    """
    def cell(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    rows = [[cell(c) for c in row] for row in rows if any(row)]
    if len(rows) < 2:
        return "\n".join(" ".join(r) for r in rows)
    header, lines = rows[0], []
    for row in rows[1:]:
        if len(row) == 2:
            lines.append(f"- {row[0]}: {row[1]}")
        else:
            pairs = "; ".join(f"{h} {v}".strip() for h, v in zip(header[1:], row[1:]) if v)
            lines.append(f"- {row[0]}: {pairs}")
    return "\n".join(lines)


def is_heading(line: str) -> bool:
    """장·조문·부칙 제목 줄. 제목 뒤에는 본문을 이어 붙이지 않는다."""
    return bool(CHAPTER_RE.match(line) or ARTICLE_RE.match(line) or SECTION_RE.match(line))


def is_structural(line: str) -> bool:
    """새 논리 줄의 시작인지. 아니면 앞 줄이 화면에서 줄바꿈된 것이다."""
    return bool(
        CHAPTER_RE.match(line)
        or ARTICLE_RE.match(line)
        or SECTION_RE.match(line)
        or DROP_FROM_RE.match(line)
        or LIST_ITEM_RE.match(line)
    )


def clean_lines(page_text: str) -> list[str]:
    """공백을 정리하고 화면 폭 때문에 끊긴 줄을 이어 붙인다."""
    out: list[str] = []
    for raw in page_text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or re.fullmatch(r"-?\s*\d+\s*-?", line):  # 빈 줄, 단독 페이지 번호
            continue
        if out and not is_structural(line) and not is_heading(out[-1]):
            sep = "" if out[-1].endswith("·") else " "
            out[-1] = f"{out[-1]}{sep}{line}"
        else:
            out.append(line)
    return out


# ---------------------------------------------------------------- 구조 분석

def parse_pdf(file_path: str | Path, source: str | None = None) -> ParsedDoc:
    source = source or Path(file_path).name
    pages = extract_pages(file_path)

    # 1쪽 첫 줄은 문서 제목, 그 아래 표지 표에서 문서번호·버전을 읽는다
    raw_first = [l.strip() for l in (pages[0] if pages else "").splitlines() if l.strip()]
    doc = raw_first[0] if raw_first else Path(source).stem
    head = "\n".join(raw_first[:15])
    doc_no = m.group(0) if (m := DOC_NO_RE.search(head)) else ""
    version = m.group(1) if (m := VERSION_RE.search(head)) else ""
    if raw_first:
        pages[0] = pages[0].split(raw_first[0], 1)[1]

    chapter = ""
    current = Section(chapter="", article="", title="문서 개요", page=1)
    sections: list[Section] = [current]

    for page_no, page_text in enumerate(pages, start=1):
        lines = clean_lines(page_text)
        # 앞 페이지에서 이어지는 문장은 직전 줄에 붙인다
        if lines and current.lines and not is_structural(lines[0]):
            sep = "" if current.lines[-1].endswith("·") else " "
            current.lines[-1] = f"{current.lines[-1]}{sep}{lines.pop(0)}"
        for line in lines:
            if DROP_FROM_RE.match(line):
                return ParsedDoc(source, doc, doc_no, version, _non_empty(sections))
            if CHAPTER_RE.match(line):
                chapter = line
                continue
            if m := ARTICLE_RE.match(line):
                current = Section(chapter, m.group(1), m.group(2).strip(), page_no)
                sections.append(current)
                continue
            if SECTION_RE.match(line):
                chapter = ""
                current = Section("", "", line, page_no)
                sections.append(current)
                continue
            if CHECKLIST_RE.match(line):  # 시행 전 체크리스트 항목
                continue
            current.lines.append(line)

    return ParsedDoc(source, doc, doc_no, version, _non_empty(sections))


def _non_empty(sections: list[Section]) -> list[Section]:
    return [s for s in sections if s.lines]


# ---------------------------------------------------------------- 청킹

def _metadata(parsed: ParsedDoc, section: Section, mode: str) -> dict:
    return {
        "source": parsed.source,
        "doc": parsed.doc,
        "doc_no": parsed.doc_no,
        "version": parsed.version,
        "doc_type": "사내규정",
        "chapter": section.chapter,
        "article": section.article,
        "title": section.title,
        "page": section.page,
        "chunk_mode": mode,
    }


def chunk_fixed(parsed: ParsedDoc) -> list[Document]:
    """문서 전체를 500/50 고정 크기로 자른다. 메타데이터는 청크 시작 위치의 조문을 따른다."""
    full, starts = "", []
    for s in parsed.sections:
        block = f"{s.label_with_aliases}\n{s.text}\n\n"
        starts.append((len(full), s))
        full += block

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=FIXED_CHUNK_SIZE,
        chunk_overlap=FIXED_CHUNK_OVERLAP,
        add_start_index=True,
    )
    docs = []
    for d in splitter.create_documents([full]):
        pos = d.metadata["start_index"]
        section = next(s for start, s in reversed(starts) if start <= pos)
        docs.append(Document(page_content=d.page_content, metadata=_metadata(parsed, section, "fixed")))
    return docs


def chunk_article(parsed: ParsedDoc) -> list[Document]:
    """조문 하나를 청크 하나로. 길면 항 단위로 묶어 나누고 앞에 조문 제목을 붙인다."""
    docs = []
    for s in parsed.sections:
        header = f"[{parsed.doc} {s.label_with_aliases}]"
        for part in _split_long(s.lines):
            docs.append(Document(page_content=f"{header}\n{part}", metadata=_metadata(parsed, s, "article")))
    return docs


def _split_long(lines: list[str]) -> list[str]:
    parts, buf = [], ""
    for line in lines:
        if buf and len(buf) + len(line) + 1 > ARTICLE_MAX_CHARS:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n{line}" if buf else line
    if buf:
        parts.append(buf)
    return parts


def chunk(parsed: ParsedDoc, mode: str | None = None) -> list[Document]:
    mode = mode or CHUNK_MODE
    if mode == "article":
        return chunk_article(parsed)
    return chunk_fixed(parsed)


# ---------------------------------------------------------------- 적재

def _chunk_ids(docs: list[Document]) -> list[str]:
    return [f"{d.metadata['source']}::{i}" for i, d in enumerate(docs)]


def load_store(path: Path | None = None, embedding=None) -> FAISS | None:
    path = path or PDF_STORE_PATH
    if (path / "index.faiss").exists() and (path / "index.pkl").exists():
        return FAISS.load_local(str(path), embeddings=embedding or embeddings(), allow_dangerous_deserialization=True)
    return None


def upsert(store: FAISS | None, docs: list[Document], embedding=None) -> FAISS:
    """같은 source 의 기존 청크를 지우고 새 청크를 추가한다. 저장소가 없으면 새로 만든다."""
    if not docs:
        raise ValueError("적재할 청크가 없습니다.")
    ids = _chunk_ids(docs)
    if store is None:
        return FAISS.from_documents(docs, embedding or embeddings(), ids=ids)

    source = docs[0].metadata["source"]
    old_ids = [doc_id for doc_id, d in store.docstore._dict.items() if d.metadata.get("source") == source]
    if old_ids:
        store.delete(old_ids)
    store.add_documents(docs, ids=ids)
    return store


def save_store(store: FAISS, path: Path | None = None) -> None:
    """새 인덱스를 별도 디렉터리에 완성한 후 교체한다. 실패하면 기존 파일을 복구한다."""
    path = (path or PDF_STORE_PATH).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and any(p.name not in {"index.faiss", "index.pkl"} for p in path.iterdir()):
        raise ValueError("Index directory contains unrelated files")
    stage = Path(tempfile.mkdtemp(prefix=f".{path.name}-stage-", dir=path.parent)).resolve()
    backup = path.with_name(f".{path.name}-backup-{uuid.uuid4().hex}").resolve()
    assert stage.parent == backup.parent == path.parent and stage != path and backup != path
    moved = False
    try:
        store.save_local(str(stage))
        if path.exists():
            path.rename(backup)
            moved = True
        try:
            stage.rename(path)
        except BaseException:
            if moved:
                backup.rename(path)
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if moved and backup.exists() and path.exists():
            shutil.rmtree(backup, ignore_errors=True)


def clone_store(store: FAISS) -> FAISS:
    """검색 중인 원본을 변경하지 않도록 인덱스와 문서 매핑을 복제한다."""
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    return FAISS(store.embedding_function, faiss.clone_index(store.index),
                 InMemoryDocstore(dict(store.docstore._dict)), dict(store.index_to_docstore_id),
                 normalize_L2=store._normalize_L2, distance_strategy=store.distance_strategy)


def count_by_source(store: FAISS) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in store.docstore._dict.values():
        src = d.metadata.get("source", "unknown")
        counts[src] = counts.get(src, 0) + 1
    return counts
