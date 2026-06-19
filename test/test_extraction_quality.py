"""
Extraction quality benchmark — measures entity and relation F1 against
test/gold_set/ground_truth.json. Always passes; prints a full scorecard
so results can be used to guide model/prompt improvements.

Run: uv run python -m pytest test/test_extraction_quality.py -v -s
"""

import unittest
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from app.services.extractor import GraphExtractor

TARGET_ENTITY_F1 = 0.70
TARGET_RELATION_F1 = 0.60


def _f1(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0, p, r


def _entity_match(ext_name, gt_entities):
    for gt in gt_entities:
        if ext_name in gt or gt in ext_name:
            return True
    return False


def _relation_match(ext_rel, gt_relations):
    for gt in gt_relations:
        if (
            (ext_rel[0] in gt[0] or gt[0] in ext_rel[0])
            and (ext_rel[1] in gt[1] or gt[1] in ext_rel[1])
            and (ext_rel[2] in gt[2] or gt[2] in ext_rel[2])
        ):
            return True
    return False


class TestExtractionQuality(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        truth_path = Path(__file__).parent / "gold_set" / "ground_truth.json"
        if not truth_path.exists():
            self.skipTest(
                "No ground_truth.json in test/gold_set — add fixtures to enable"
            )
        self.gold_dir = truth_path.parent
        with open(truth_path, encoding="utf-8") as f:
            self.ground_truth = json.load(f)

    def test_extraction_quality(self):
        """Benchmark extractor F1. Always passes — results are for optimization."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not set")

        extractor = GraphExtractor(api_key=self.api_key)

        total = {
            "ent_tp": 0,
            "ent_fp": 0,
            "ent_fn": 0,
            "rel_tp": 0,
            "rel_fp": 0,
            "rel_fn": 0,
        }
        per_doc = {}

        for fname, truth in self.ground_truth.items():
            fpath = self.gold_dir / fname
            content = fpath.read_text(encoding="utf-8")
            result = extractor.extract(content)

            gt_ents = {e["name"].lower().strip() for e in truth["entities"]}
            gt_rels = {
                (
                    r["source"].lower().strip(),
                    r["predicate"].lower().strip(),
                    r["target"].lower().strip(),
                )
                for r in truth["relations"]
            }
            ext_ents = {e.name.lower().strip() for e in result.entities}
            ext_rels = {
                (
                    r.source.lower().strip(),
                    r.predicate.lower().strip(),
                    r.target.lower().strip(),
                )
                for r in result.relations
            }

            e_tp = sum(1 for e in ext_ents if _entity_match(e, gt_ents))
            e_fp = len(ext_ents) - e_tp
            e_fn = sum(1 for g in gt_ents if not _entity_match(g, ext_ents))

            r_tp = sum(1 for r in ext_rels if _relation_match(r, gt_rels))
            r_fp = len(ext_rels) - r_tp
            r_fn = sum(1 for g in gt_rels if not _relation_match(g, ext_rels))

            ef1, ep, er = _f1(e_tp, e_fp, e_fn)
            rf1, rp, rr = _f1(r_tp, r_fp, r_fn)
            per_doc[fname] = {
                "entity_f1": ef1,
                "relation_f1": rf1,
                "entity_precision": ep,
                "entity_recall": er,
                "relation_precision": rp,
                "relation_recall": rr,
                "missed_entities": [
                    g for g in gt_ents if not _entity_match(g, ext_ents)
                ],
                "extra_entities": [
                    e for e in ext_ents if not _entity_match(e, gt_ents)
                ],
                "missed_relations": [
                    g for g in gt_rels if not _relation_match(g, ext_rels)
                ],
                "extra_relations": [
                    r for r in ext_rels if not _relation_match(r, gt_rels)
                ],
            }

            for k, v in [
                ("ent_tp", e_tp),
                ("ent_fp", e_fp),
                ("ent_fn", e_fn),
                ("rel_tp", r_tp),
                ("rel_fp", r_fp),
                ("rel_fn", r_fn),
            ]:
                total[k] += v

        global_ef1, global_ep, global_er = _f1(
            total["ent_tp"], total["ent_fp"], total["ent_fn"]
        )
        global_rf1, global_rp, global_rr = _f1(
            total["rel_tp"], total["rel_fp"], total["rel_fn"]
        )

        # ── Scorecard ─────────────────────────────────────────────────────────
        sep = "=" * 60
        print(f"\n{sep}")
        print("  EXTRACTION QUALITY SCORECARD")
        print(sep)

        for fname, s in per_doc.items():
            status_e = "✅" if s["entity_f1"] >= TARGET_ENTITY_F1 else "⚠️ "
            status_r = "✅" if s["relation_f1"] >= TARGET_RELATION_F1 else "⚠️ "
            print(f"\n  [{fname}]")
            print(
                f"    Entities  {status_e}  P={s['entity_precision']:.2f}  R={s['entity_recall']:.2f}  F1={s['entity_f1']:.2f}  (target {TARGET_ENTITY_F1})"
            )
            print(
                f"    Relations {status_r}  P={s['relation_precision']:.2f}  R={s['relation_recall']:.2f}  F1={s['relation_f1']:.2f}  (target {TARGET_RELATION_F1})"
            )
            if s["missed_entities"]:
                print(f"    Missed entities : {s['missed_entities']}")
            if s["extra_entities"]:
                print(f"    Extra entities  : {s['extra_entities']}")
            if s["missed_relations"]:
                print(
                    f"    Missed relations: {[str(r) for r in s['missed_relations']]}"
                )

        status_ge = "✅" if global_ef1 >= TARGET_ENTITY_F1 else "⚠️ "
        status_gr = "✅" if global_rf1 >= TARGET_RELATION_F1 else "⚠️ "
        print(f"\n{sep}")
        print("  OVERALL")
        print(
            f"    Entities  {status_ge}  P={global_ep:.2f}  R={global_er:.2f}  F1={global_ef1:.2f}  (target {TARGET_ENTITY_F1})"
        )
        print(
            f"    Relations {status_gr}  P={global_rp:.2f}  R={global_rr:.2f}  F1={global_rf1:.2f}  (target {TARGET_RELATION_F1})"
        )
        print(sep)

        # Store on self so callers can inspect programmatically
        self.entity_f1 = global_ef1
        self.relation_f1 = global_rf1
        self.per_doc = per_doc
        # This test never hard-fails — results drive optimization, not CI gates


if __name__ == "__main__":
    unittest.main(verbosity=2)
