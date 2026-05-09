from rank_bm25 import BM25Okapi
import re

TOKEN_PATTERN = re.compile(r"\w+")

class BM25Store:

    def __init__(self, items):

        self.items = items

        self.by_name = {
            item.name.lower().strip(): item
            for item in items
        }

        self.documents = [
            self.tokenize(
                item.searchable_text()
            )
            for item in items
        ]

        self.bm25 = BM25Okapi(
            self.documents
        )

    def tokenize(self, text: str):

        return TOKEN_PATTERN.findall(
            text.lower()
        )

    def search(
        self,
        query: str,
        k: int = 10
    ):

        tokens = self.tokenize(query)

        scores = self.bm25.get_scores(
            tokens
        )

        ranked = sorted(
            zip(self.items, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return ranked[:k]