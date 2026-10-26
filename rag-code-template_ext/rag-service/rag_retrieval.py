"""명시한 규정·조항의 정확 조회. 코퍼스 스냅샷마다 메타데이터 매핑을 한 번 만든다."""
import re
import threading
from dataclasses import dataclass

from rag_agent import RetrievalError

DOC = re.compile(r'(취업|복리후생|근태|휴가|출장)\s*규정')
ARTICLE = re.compile(r'(?:제\s*)?(\d+)\s*조(?:\s*의\s*(\d+))?')


@dataclass(frozen=True)
class SearchTarget:
    documents: tuple[str, ...]
    articles: tuple[str, ...]


def search_target(question):
    articles = tuple(dict.fromkeys('제' + str(int(a)) + '조' + ('의' + str(int(b)) if b else '')
                                   for a, b in ARTICLE.findall(question)))
    if not articles:
        return None
    documents = tuple(dict.fromkeys(m + '규정' for m in DOC.findall(question)))
    return SearchTarget(documents, articles)


def document_name(value):
    compact = re.sub(r'\s+', '', str(value))
    match = DOC.search(compact)
    return match.group(1) + '규정' if match else compact


class MetadataLookup:
    """FAISS의 전체 docstore로 매핑한다. 유사도 후보 fetch_k에 의존하지 않는다.

    인덱스가 교체되면 새 RagService가 만들어지는 런타임 계약을 따른다.
    정확 조회를 지원하지 않는 저장소는 검색 실패로 알리고 의미 검색으로 대체하지 않는다.
    """
    def __init__(self, store):
        self.store = store
        self._by_article = None
        self._lock = threading.Lock()

    def find(self, target):
        with self._lock:
            if self._by_article is None:
                mapping = getattr(self.store, 'index_to_docstore_id', None)
                docstore = getattr(self.store, 'docstore', None)
                if mapping is None or not callable(getattr(docstore, 'search', None)):
                    raise RetrievalError('Exact article lookup requires an indexed docstore')
                by_article = {}
                for key in mapping.values():
                    document = docstore.search(key)
                    if isinstance(document, str):
                        raise RetrievalError('Indexed document is unavailable')
                    metadata = document.metadata
                    article = re.sub(r'\s+', '', str(metadata.get('article', '')))
                    by_article.setdefault(article, []).append(document)
                self._by_article = by_article
        documents = [doc for article in target.articles for doc in self._by_article.get(article, [])
                     if not target.documents or document_name(doc.metadata.get('doc', '')) in target.documents]
        names = sorted({str(doc.metadata.get('doc', '등록 문서')) for doc in documents})
        if not target.documents and len(names) > 1:
            return [], '어느 규정의 조항을 확인할까요? ' + ', '.join(names)
        if len(documents) > 50:
            raise RetrievalError('Explicit article context exceeds document limit')
        # 점수는 유사도가 아니라 정확 매칭용 자리표시자이며 신뢰도로 해석하지 않는다.
        return [(doc, 0.0) for doc in documents], None
