# PoC analýzátoru právních rizik ve smlouvách

Tento Proof of Concept má za cíl vytvořit produkt, který uživateli pomůže rozhodnout, zda podepsat smlouvu, na základě analýzy právních rizik v dokumentu. Hlavním zaměřením je nahrazení nákladné právní konzultace softwarem, který identifikuje rizikové faktory ve smlouvě a poskytne doporučení na základě vážnosti těchto rizik.

## Postup

### 1. Načtení smlouvy a extrakce textu z PDF
- **Cíl**: Extrahovat text ze smlouvy ve formátu PDF.
- **Postup**: 
    - Použití knihovny `pdfminer` k převedení textu z PDF do formátu vhodného pro zpracování.
    - Funkce `extract_text_from_pdf(pdf_path)` načte text z PDF souboru na základě cesty k souboru, kterou uživatel zadá.
    - V případě chyby během načítání PDF je chyba logována a proces se zastaví.

### 2. Rozdělení textu na paragrafy
- **Cíl**: Rozdělit text smlouvy na jednotlivé paragrafy, aby bylo možné analyzovat každý paragraf zvlášť.
- **Postup**: 
    - Použití regulárního výrazu, který detekuje číslování odstavců a rozděluje text na paragrafy. 
    - Funkce `split_text_into_paragraphs(text)` kontroluje každou řádku textu a pokud obsahuje číslovaný odstavec, uloží jej jako nový paragraf.

### 3. Vytvoření vektorového uložiště
- **Cíl**: Umožnit pokročilou analýzu textu smlouvy pomocí semantického vyhledávání.
- **Postup**: 
    - Vytvoření vektorového uložiště s využitím `FAISS`, který umožňuje efektivní vyhledávání podobných částí textu na základě dotazů.
    - Funkce `create_vector_store(paragraphs, embeddings)` používá knihovnu `OpenAIEmbeddings` k vytvoření vektorů z odstavců a následně je uloží do FAISS indexu.
    - Metadata každého paragrafu jsou uložena, aby bylo možné přiřadit nalezené výsledky ke konkrétním částem smlouvy.

### 4. Identifikace rizik pomocí přesného shodování klíčových slov
- **Cíl**: Najít rizikové faktory ve smlouvě na základě předem definovaných klíčových slov.
- **Postup**: 
    - Funkce `strict_keyword_matching(paragraphs, RISK_FACTORS)` prochází každý paragraf a porovnává text s definovaným slovníkem rizikových faktorů.
    - Pokud je nalezena shoda mezi paragrafem a některým z klíčových slov (např. "výpověď", "pokuta", "omezení práv"), riziko je zaznamenáno včetně typu rizika, váhy a popisu.

### 5. Identifikace rizik pomocí semantického vyhledávání
- **Cíl**: Umožnit pokročilejší analýzu rizik, kdy nejsou klíčová slova přímo obsažena, ale májí v textu podobný význam.
- **Postup**:
    - Pomocí modelu `OpenAI` je vytvořen řetězec pro vyhledávání `RetrievalQAWithSourcesChain`.
    - Funkce `semantic_search(paragraphs, vectorstore, RISK_FACTORS, llm)` generuje dotazy na základě rizikových faktorů (např. "Najděte zmínky o 'výpovědi' v tomto textu.") a spustí semantické vyhledávání.
    - Výsledky jsou zpracovány a přidány do seznamu rizik.

### 6. Sloučení výsledků přesného a semantického vyhledávání
- **Cíl**: Zkombinovat výsledky z přesného shodování klíčových slov a semantického vyhledávání do jednoho seznamu.
- **Postup**:
    - Funkce `merge_risks(risks1, risks2)` sloučí rizika ze dvou metod a odstraní duplicity.

### 7. Výpočet celkové váhy rizik a poskytnutí doporučení
- **Cíl**: Na základě nalezených rizik a jejich váhy poskytnout doporučení, zda uživatel má smlouvu podepsat nebo ne.
- **Postup**:
    - Celková váha rizik je vypočtena jako součet jednotlivých vah rizik.
    - Pokud je váha vyšší nebo rovna prahové hodnotě (např. 20), je doporučeno smlouvu nepodepisovat.
  
### 8. Uložení zprávy
- **Cíl**: Vytvořit výstupní zprávu, která shrne nalezená rizika a poskytne jasné doporučení.
- **Postup**:
    - Do souboru se zapíše seznam nalezených rizik, jejich popis, váha a zdroj (odstavec smlouvy).
    - Dále se zapíše celková váha rizik a finální doporučení: zda smlouvu podepsat nebo ne.

## Závěr
Tento PoC poskytuje základní mechanismus pro analýzu právních rizik ve smlouvách. Pomocí kombinace klíčového slova shodování a semantického vyhledávání je možné identifikovat rizikové části textu a poskytnout uživateli doporučení. Produkt má potenciál nahradit některé drahé právní služby a umožnit uživatelům rychle a levně analyzovat smlouvy.
