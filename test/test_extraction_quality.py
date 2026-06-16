import unittest
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from app.services.extractor import GraphExtractor


class TestExtractionQuality(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.test_dir = Path(__file__).parent / "gold_set"

        # Load ground truth
        truth_path = self.test_dir / "ground_truth.json"
        with open(truth_path, "r", encoding="utf-8") as f:
            self.ground_truth = json.load(f)

    def test_extraction_precision_recall_f1(self):
        """Runs the extractor on gold standard docs and verifies F1 score > 0.7."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in env. Skipping quality check.")

        extractor = GraphExtractor(api_key=self.api_key)

        total_tp_entities = 0
        total_fp_entities = 0
        total_fn_entities = 0

        total_tp_relations = 0
        total_fp_relations = 0
        total_fn_relations = 0

        for file_name, truth in self.ground_truth.items():
            file_path = self.test_dir / file_name
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            print(f"\nEvaluating extraction quality for: {file_name}")
            result = extractor.extract(content)

            # Ground truth entities & relations
            gt_entities = {
                e["name"].lower().strip(): e["type"] for e in truth["entities"]
            }
            gt_relations = {
                (
                    r["source"].lower().strip(),
                    r["predicate"].lower().strip(),
                    r["target"].lower().strip(),
                )
                for r in truth["relations"]
            }

            # Extracted entities & relations
            ext_entities = {e.name.lower().strip(): e.type for e in result.entities}
            ext_relations = {
                (
                    r.source.lower().strip(),
                    r.predicate.lower().strip(),
                    r.target.lower().strip(),
                )
                for r in result.relations
            }

            # --- Entity Evaluation ---
            tp_entities = 0
            fp_entities = 0
            fn_entities = 0

            for name, etype in ext_entities.items():
                # Fuzzy matching: check if name is in ground truth
                matched = False
                for gt_name in gt_entities:
                    if name in gt_name or gt_name in name:
                        tp_entities += 1
                        matched = True
                        break
                if not matched:
                    fp_entities += 1

            for gt_name in gt_entities:
                matched = False
                for name in ext_entities:
                    if name in gt_name or gt_name in name:
                        matched = True
                        break
                if not matched:
                    fn_entities += 1

            total_tp_entities += tp_entities
            total_fp_entities += fp_entities
            total_fn_entities += fn_entities

            print(f"Entities: TP={tp_entities}, FP={fp_entities}, FN={fn_entities}")

            # --- Relation Evaluation ---
            tp_relations = 0
            fp_relations = 0
            fn_relations = 0

            # Match relations
            for ext_rel in ext_relations:
                # check if there's any relation in gt that matches
                matched = False
                for gt_rel in gt_relations:
                    # Allow sub-string name matching for source and target
                    src_match = ext_rel[0] in gt_rel[0] or gt_rel[0] in ext_rel[0]
                    tgt_match = ext_rel[2] in gt_rel[2] or gt_rel[2] in ext_rel[2]
                    pred_match = ext_rel[1] in gt_rel[1] or gt_rel[1] in ext_rel[1]

                    if src_match and tgt_match and pred_match:
                        tp_relations += 1
                        matched = True
                        break
                if not matched:
                    fp_relations += 1

            for gt_rel in gt_relations:
                matched = False
                for ext_rel in ext_relations:
                    src_match = ext_rel[0] in gt_rel[0] or gt_rel[0] in ext_rel[0]
                    tgt_match = ext_rel[2] in gt_rel[2] or gt_rel[2] in ext_rel[2]
                    pred_match = ext_rel[1] in gt_rel[1] or gt_rel[1] in ext_rel[1]

                    if src_match and tgt_match and pred_match:
                        matched = True
                        break
                if not matched:
                    fn_relations += 1

            total_tp_relations += tp_relations
            total_fp_relations += fp_relations
            total_fn_relations += fn_relations

            print(f"Relations: TP={tp_relations}, FP={fp_relations}, FN={fn_relations}")

        # Calculate global Entity F1
        entity_precision = (
            total_tp_entities / (total_tp_entities + total_fp_entities)
            if (total_tp_entities + total_fp_entities) > 0
            else 0
        )
        entity_recall = (
            total_tp_entities / (total_tp_entities + total_fn_entities)
            if (total_tp_entities + total_fn_entities) > 0
            else 0
        )
        entity_f1 = (
            2 * entity_precision * entity_recall / (entity_precision + entity_recall)
            if (entity_precision + entity_recall) > 0
            else 0
        )

        # Calculate global Relation F1
        relation_precision = (
            total_tp_relations / (total_tp_relations + total_fp_relations)
            if (total_tp_relations + total_fp_relations) > 0
            else 0
        )
        relation_recall = (
            total_tp_relations / (total_tp_relations + total_fn_relations)
            if (total_tp_relations + total_fn_relations) > 0
            else 0
        )
        relation_f1 = (
            2
            * relation_precision
            * relation_recall
            / (relation_precision + relation_recall)
            if (relation_precision + relation_recall) > 0
            else 0
        )

        print("\n--- Combined Quality Report ---")
        print(
            f"Entity Precision: {entity_precision:.2f} | Recall: {entity_recall:.2f} | F1: {entity_f1:.2f}"
        )
        print(
            f"Relation Precision: {relation_precision:.2f} | Recall: {relation_recall:.2f} | F1: {relation_f1:.2f}"
        )

        # Assert F1 is greater than target (0.7) for entities
        self.assertGreaterEqual(
            entity_f1,
            0.70,
            f"Entity extraction quality F1 ({entity_f1:.2f}) is below target 0.70",
        )


if __name__ == "__main__":
    unittest.main()
