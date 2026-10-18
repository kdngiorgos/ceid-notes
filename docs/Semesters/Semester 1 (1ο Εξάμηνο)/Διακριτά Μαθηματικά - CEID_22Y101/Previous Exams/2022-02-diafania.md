---
course: CEID_22Y101
session: 2022-02-diafania
label: Φεβρουάριος 2022 — μεμονωμένη ερώτηση (διαφάνεια)
sources:
- 1.png
format: open
duration_min: null
notes: Μεμονωμένη φωτογραφία ερώτησης σε μορφή διαφάνειας (2 μονάδες). Δεν αντιστοιχεί σε καμία από τις ομάδες της 08/02/2022· η προέλευση δεν είναι βέβαιη.
transcription: verbatim
solutions: ai-unverified
---
# Διακριτά Μαθηματικά — Φεβρουάριος 2022 — μεμονωμένη ερώτηση

> Μεταγραφή από τη φωτογραφία 1.png.

## 1.png

(2 Μονάδες)

Χρησιμοποιώντας την αρχή του Εγκλεισμού-Αποκλεισμού, υπολογίστε πόσοι ακέραιοι μεταξύ του 1 και του 110 είναι σχετικά πρώτοι με το 110.

??? success "Λύσεις (⚪ AI, μη επαληθευμένο)"
    **Κατάσταση:** ⚪ AI, μη επαληθευμένο
    Πηγή: λύσεις AI (sonnet), ανεξάρτητη επανάληψη και αντιπαραβολή· καμία δεν έχει ελεγχθεί από άνθρωπο

    !!! warning "Προσοχή"
        Λύση από AI — ελέγξτε την· δεν έχει επαληθευτεί από άνθρωπο. Η ένδειξη «δύο λύσεις συμφωνούν» δεν σημαίνει ότι η απάντηση είναι σωστή.

    # AI λύσεις — 2022-02-diafania

    > Οι λύσεις γράφτηκαν από μοντέλα AI και δεν έχουν ελεγχθεί από άνθρωπο. Η αρίθμηση ακολουθεί το αρχείο θεμάτων.

    ## Θέμα 1 (πλήθος σχετικά πρώτων με το 110)

    *Αξιοπιστία: μία λύση AI, δεν έχει αντιπαραβληθεί με δεύτερη · εμπιστοσύνη λύτη: υψηλή*

    $110=2\cdot5\cdot11$. Έστω $A_2,A_5,A_{11}$ τα σύνολα των πολλαπλασίων του $2,5,11$ στο $\{1,\dots,110\}$. Τότε $|A_2|=55,\ |A_5|=22,\ |A_{11}|=10$, $|A_2\cap A_5|=11,\ |A_2\cap A_{11}|=5,\ |A_5\cap A_{11}|=2,\ |A_2\cap A_5\cap A_{11}|=1$.

    Εγκλεισμός–Αποκλεισμός:
    $$|A_2\cup A_5\cup A_{11}|=55+22+10-11-5-2+1=70.$$
    Σχετικά πρώτοι: $110-70=\mathbf{40}$ (ισούται με $\varphi(110)=110\cdot\tfrac12\cdot\tfrac45\cdot\tfrac{10}{11}$, επαλήθευση σε Python: 40).

    [✔ Επιβεβαίωσε](https://github.com/kdngiorgos/ceid-notes/issues/new?template=verify-solution.yml&title=%CE%95%CF%80%CE%B9%CE%B2%CE%B5%CE%B2%CE%B1%CE%AF%CF%89%CF%83%CE%B7%20%CE%BB%CF%8D%CF%83%CE%B7%CF%82%3A%20CEID_22Y101%202022-02-diafania&course=CEID_22Y101&session=2022-02-diafania) · [✖ Βρήκα λάθος](https://github.com/kdngiorgos/ceid-notes/issues/new?template=fix-mistake.yml&title=%CE%9B%CE%AC%CE%B8%CE%BF%CF%82%20%CF%83%CF%84%CE%B9%CF%82%20%CE%BB%CF%8D%CF%83%CE%B5%CE%B9%CF%82%3A%20CEID_22Y101%202022-02-diafania&course=CEID_22Y101&session=2022-02-diafania)

---
[✖ Βρήκα λάθος στη μεταγραφή](https://github.com/kdngiorgos/ceid-notes/issues/new?template=fix-mistake.yml&title=%CE%9B%CE%AC%CE%B8%CE%BF%CF%82%20%CF%83%CF%84%CE%B7%20%CE%BC%CE%B5%CF%84%CE%B1%CE%B3%CF%81%CE%B1%CF%86%CE%AE%3A%20CEID_22Y101%202022-02-diafania&course=CEID_22Y101&session=2022-02-diafania)
