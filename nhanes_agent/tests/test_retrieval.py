import unittest
from unittest import mock

from nhanes_agent.app.core.config import RetrievalWeights
from nhanes_agent.app.services.retrieval.hybrid_retriever import search_chunks


class RetrievalTests(unittest.TestCase):
    def test_hybrid_ranking_boosts_entity_overlap_chunks(self) -> None:
        def fake_vector(query, project_name, paper_slug, top_k):
            return [{"chunk_id": "p:s:1", "document_id": "p:s", "section": "Methods", "chunk_index": 1, "chunk_text": "RIDAGEYR BMI", "vector_score": 0.2, "lexical_score": 0.0, "entity_overlap_score": 0.0, "metadata_boost": 0.0}]

        def fake_lexical(query, project_name, paper_slug, top_k, base_dir=None):
            return [{"chunk_id": "p:s:1", "document_id": "p:s", "section": "Methods", "chunk_index": 1, "chunk_text": "RIDAGEYR BMI", "vector_score": 0.0, "lexical_score": 0.8, "entity_overlap_score": 0.0, "metadata_boost": 0.0}]

        with mock.patch("nhanes_agent.app.services.retrieval.hybrid_retriever.retrieve_vector_chunks", side_effect=fake_vector):
            with mock.patch("nhanes_agent.app.services.retrieval.hybrid_retriever.retrieve_lexical_chunks", side_effect=fake_lexical):
                rows = search_chunks("RIDAGEYR BMI", {"cycle": None, "component": None}, project_name="p", paper_slug="s", top_k=5, weights=RetrievalWeights(), base_dir=None)
        self.assertGreater(rows[0]["hybrid_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
