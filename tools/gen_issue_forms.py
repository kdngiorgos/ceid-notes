"""Generate .github/ISSUE_TEMPLATE/upload-exam.yml from the master repo's catalog/registry.json.

    python tools/gen_issue_forms.py --registry D:/CEID/Classes/catalog/registry.json

The registry is only read; it is not part of this repository. Re-run after courses change.
"""
import argparse, json, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / ".github" / "ISSUE_TEMPLATE" / "upload-exam.yml"
CATEGORY_ORDER = [("elective", "Επιλογής"), ("general-education", "Γεν. Παιδείας"), ("old-curriculum", "Παλαιό ΠΣ")]
OTHER = "Άλλο / δεν υπάρχει στη λίστα (γράψε το στην περιγραφή)"


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)      # JSON strings are valid YAML double-quoted scalars


def course_options(courses: list[dict]) -> list[str]:
    groups: list[tuple[str, list[dict]]] = []
    for sem in range(1, 10):
        groups.append((f"Εξ.{sem}", [c for c in courses if c["category"] == "core" and c.get("semester") == sem]))
    for cat, label in CATEGORY_ORDER:
        groups.append((label, [c for c in courses if c["category"] == cat]))
    opts: list[str] = []
    for label, cs in groups:
        for c in sorted(cs, key=lambda c: c["title"]):
            code = c.get("code") or ""
            opts.append(f"[{label}] {c['title']}" + (f" ({code})" if code else ""))
    seen: dict[str, int] = {}
    uniq = []
    for o in opts:
        seen[o] = seen.get(o, 0) + 1
        uniq.append(o if seen[o] == 1 else f"{o} #{seen[o]}")
    return uniq + [OTHER]


def render(options: list[str]) -> str:
    opt_lines = "\n".join(f"        - {q(o)}" for o in options)
    return f"""name: "Ανέβασμα θεμάτων εξέτασης"
description: "Έχεις θέματα, φωτογραφίες ή θυμάσαι τι έπεσε; Στείλ' τα εδώ."
title: "[Θέματα] "
labels: ["upload"]
body:
  - type: markdown
    attributes:
      value: |
        Ευχαριστούμε! Ο διαχειριστής θα μεταγράψει και θα ελέγξει το υλικό πριν δημοσιευτεί.
        Δεν έχεις λογαριασμό GitHub; Φτιάξε έναν δωρεάν ή στείλε τα αρχεία στον διαχειριστή ή σε κάποιον φίλο σου που τον έχει.
  - type: dropdown
    id: course
    attributes:
      label: Μάθημα
      description: "Ομαδοποιημένα ανά εξάμηνο / κατηγορία. Πάτα στη λίστα και πληκτρολόγησε για αναζήτηση."
      options:
{opt_lines}
    validations:
      required: true
  - type: input
    id: date
    attributes:
      label: Ημερομηνία εξέτασης (μήνας/έτος)
      placeholder: "π.χ. 06/2025"
    validations:
      required: true
  - type: dropdown
    id: kind
    attributes:
      label: Τύπος
      options:
        - Θεωρία
        - Εργαστήριο
        - Πρόοδος
        - Άλλο
    validations:
      required: true
  - type: textarea
    id: files
    attributes:
      label: Φωτογραφίες / PDF
      description: "Σύρε τα αρχεία εδώ ή επικόλλησε link (Drive κ.λπ.)."
  - type: textarea
    id: recall
    attributes:
      label: Θυμάμαι τα θέματα
      description: "Αν δεν έχεις αρχείο, γράψε ό,τι θυμάσαι (και πόσο σίγουρος είσαι)."
  - type: input
    id: credit
    attributes:
      label: Όνομα για credit (προαιρετικό)
      description: "GitHub handle ή ψευδώνυμο· θα εμφανιστεί στη σελίδα ευχαριστιών."
  - type: checkboxes
    id: consent
    attributes:
      label: Συναίνεση
      options:
        - label: "Δεν περιέχει ονόματα, ΑΜ ή τηλέφωνα (τα έχω καλύψει) και δεν είναι διαφάνειες καθηγητών."
          required: true
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    courses = json.loads(Path(a.registry).read_text(encoding="utf-8"))["courses"]
    opts = course_options(courses)
    Path(a.out).write_text(render(opts), encoding="utf-8", newline="\n")
    print(f"{len(opts) - 1} courses -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
