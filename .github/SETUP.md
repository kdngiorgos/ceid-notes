# Οδηγίες διαχειριστή (owner only)

Αυτό το αποθετήριο παράγεται από το ιδιωτικό master με `tools/build_public_repo.py`. Handle: `kdngiorgos` · repo: `ceid-notes` · site: `https://ceid.gr/` · DOI: `10.5281/zenodo.23434966`.

## Ενημέρωση (νέα έκδοση)
1. Στο master: ξαναχτίσε τους οδηγούς (`tools/build_study_pdf.py <CODE>`), μετά `tools/build_public_repo.py --out <αυτός ο φάκελος>` (κρατά το `.git`, αντικαθιστά τα υπόλοιπα, γράφει τα PDF στο `_work/release-assets/` του master).
2. `git add -A && git commit && git push` (η ruleset `protect-main` επιτρέπει push μόνο στον admin· οι υπόλοιποι περνούν από Pull Request).
3. Νέο release με τα PDF: `gh release create vX.Y --title "CEID Notes X.Y" --notes "…" <master>/_work/release-assets/*.pdf`. Οι σύνδεσμοι «λήψη» δείχνουν στο `releases/latest/download/<CODE>.pdf`, οπότε ενημερώνονται μόνοι τους.
4. Νέα έκδοση στο Zenodo (New version) και ανέβασμα των ίδιων PDF.

## Στατιστικά
- Λήψεις PDF: GitHub Releases (αριθμός λήψεων ανά αρχείο, `gh release view --json assets`).
- Επισκέψεις σελίδων και κλικ σε αρχεία (pdf/zip): GoatCounter, `https://kdngiorgos.goatcounter.com`. Ανώνυμο, χωρίς cookies.
- Zenodo: προβολές και λήψεις στη σελίδα της εγγραφής.

## Ρυθμίσεις που έγιναν
Pages από GitHub Actions · labels `upload`, `fix`, `verify`, `info` · ruleset `protect-main` (PR, 1 έγκριση, έλεγχος από Code Owner, απαιτούμενο check `check`, όχι force-push/διαγραφή· bypass για admin) · Settings > Actions > Fork pull request workflows: ζήτα έγκριση για νέους συνεισφέροντες.

## Συντήρηση
- Μετά από αλλαγές στο registry: `python tools/gen_issue_forms.py --registry <registry.json>`.
- Μην κάνεις χειροκίνητες αλλαγές εδώ χωρίς να τις περάσεις και στο master: το επόμενο build τις αντικαθιστά.
