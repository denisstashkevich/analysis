import os
import sys
import re
import logging
from dotenv import load_dotenv
from pdfminer.high_level import extract_text
from langchain.chains import RetrievalQAWithSourcesChain
from langchain_openai import OpenAIEmbeddings, OpenAI
from langchain_community.vectorstores import FAISS
import subprocess

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

load_dotenv()

# Nastavení OpenAI API klíče z prostředí
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # Nezapomeňte vytvořit svůj .env soubor s klíčem
if not OPENAI_API_KEY:
    logging.error("Nebyl nalezen klíč OPENAI_API_KEY v prostředí.")
    sys.exit(1)
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

# Slovník rizikových faktorů
RISK_FACTORS = {
    'vypověď': {
        'subtypes': {
            'bez udání důvodu': {
                'weight': 20,
                'description': 'Možnost vypovědět smlouvu bez uvedení důvodu je velkým rizikem.'
            },
            'jednostranné vypovězení': {
                'weight': 3,
                'description': 'Jednostranné vypovězení smlouvy může být zneužitelné.'
            },
        },
        'weight': 5,
        'description': 'Různé formy výpovědi smlouvy mohou obsahovat rizikové prvky.'
    },
    'pokuta': {
        'subtypes': {
            'za prodlení': {
                'weight': 3,
                'description': 'Nepřiměřeně vysoké pokuty za prodlení mohou být nepřijemné.'
            },
            'za opožděnou platbu': {
                'weight': 3,
                'description': 'Pokuty za opožděné platby mohou být zneužitelné.'
            },
        },
        'weight': 3,
        'description': 'Pokuty mohou být rizikovými prvky, pokud nejsou spravedlivě nastaveny.'
    },
    'omezení práv': {
        'subtypes': {
            'právního nároku': {
                'weight': 5,
                'description': 'Omezení právního nároku nájemce může být nespravedlivé.'
            },
        },
        'weight': 5,
        'description': 'Omezení právního nároku nájemce může být nespravedlivé.'
    },
    'rozhodčí doložka': {
        'subtypes': {},
        'weight': 3,
        'description': 'Rozhodčí doložky mohou omezit právo na právní ochranu.'
    },
    'zpoplatnění údržby': {
        'subtypes': {
            'běžné údržby': {
                'weight': 2,
                'description': 'Poplatky za běžnou údržbu by měly být hrazeny pronajímatelem.'
            },
        },
        'weight': 2,
        'description': 'Poplatky za údržbu mohou být rizikovým prvkem, pokud nejsou spravedlivé.'
    },
    'pojištění': {
        'weight': 2,
        'description': 'Požadavek na sjednání pojištění může být zbytečný'
    },
}

# Cesta k PDF souboru a výstupnímu reportu
PDF_PATH = input("Zadejte cestu k PDF souboru: ")
OUTPUT_REPORT_PATH = 'analyza_smlouvy_zprava.txt'  # Cesta k výstupnímu textovému souboru

# Prahová hodnota pro doporučení
WEIGHT_THRESHOLD = int(input("Zvolte prahovou hodnotu (doporučená hodnota je 20): "))

def extract_text_from_pdf(pdf_path):
    """Extrakce textu z PDF souboru."""
    try:
        text = extract_text(pdf_path)
        logging.info("Text úspěšně extrahován z PDF.")
        return text
    except Exception as e:
        logging.error(f"Chyba při čtení PDF: {e}")
        return ""

def split_text_into_paragraphs(text):
    """Rozdělení textu na paragrafy podle číslování."""
    paragraph_pattern = r'^(\d+\.\d*(?:\.\d+)*)\.'
    lines = text.splitlines()
    paragraphs = []
    current_paragraph = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(paragraph_pattern, line):
            if current_paragraph:
                paragraphs.append(current_paragraph.strip())
            current_paragraph = line
        else:
            current_paragraph += " " + line

    if current_paragraph:
        paragraphs.append(current_paragraph.strip())

    logging.info(f"Text rozdělen na {len(paragraphs)} paragrafů.")
    return paragraphs

def create_vector_store(paragraphs, embeddings):
    """Vytvoření FAISS vektorového uložiště."""
    metadatas = []
    for para in paragraphs:
        match = re.match(r'^(\d+(?:\.\d+)*)\.', para)
        section_number = match.group(1) if match else 'Unknown'
        metadatas.append({"source": section_number})

    try:
        vectorstore = FAISS.from_texts(paragraphs, embeddings, metadatas=metadatas)
        logging.info(f"Vectorstore obsahuje {len(vectorstore.index_to_docstore_id)} dokumentů.")
    except Exception as e:
        logging.error(f"Chyba při vytváření vektorového uložiště: {e}")
        return None

    return vectorstore

def strict_keyword_matching(paragraphs, risk_factors):
    """Identifikace rizik pomocí přesného shodování klíčových slov."""
    identified_risks = []
    section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\.')

    for paragraph in paragraphs:
        para_lower = paragraph.lower()
        match = section_pattern.match(paragraph)
        section_number = match.group(1) if match else 'Unknown'

        for factor, details in risk_factors.items():
            if factor.lower() in para_lower:
                identified_risks.append({
                    'risk': factor,
                    'weight': details['weight'],
                    'description': details['description'],
                    'type': 'Přesné shodování',
                    'source': section_number
                })

            for subtype, subdetails in details.get('subtypes', {}).items():
                if subtype.lower() in para_lower:
                    identified_risks.append({
                        'risk': subtype,
                        'weight': subdetails['weight'],
                        'description': subdetails['description'],
                        'type': 'Přesné shodování',
                        'source': section_number
                    })

    return identified_risks

def semantic_search(paragraphs, vectorstore, risk_factors, llm):
    """Semantické vyhledávání rizik a integrace výsledků do reportu."""
    identified_risks = []
    semanticke_vyhledani = []

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    chain = RetrievalQAWithSourcesChain.from_llm(llm=llm, retriever=retriever)

    for risk, details in risk_factors.items():
        query = f"Najděte zmínky o '{risk}' v tomto textu."
        logging.info(f"Dotaz: {query}")

        try:
            response = chain.invoke({"question": query})
            answer = response.get("answer", "").strip()
            logging.info(f"Odpověď:  {answer}")

            semanticke_vyhledani.append({
                'question': query,
                'answer': answer
            })

            if "nenalezeno" not in answer and "není" not in answer and len(answer) > 0:
                source_docs = response.get("source_documents", [])
                logging.info(f"Nalezené zdroje pro '{risk}': {[doc.metadata.get('source', 'Unknown') for doc in source_docs]}")

                for doc in source_docs:
                    section = doc.metadata.get('source', 'Unknown')
                    identified_risks.append({
                        'risk': risk,
                        'weight': details.get('weight', 1),
                        'description': details.get('description', ''),
                        'type': 'Semantické vyhledávání',
                        'source': section
                    })
        except Exception as e:
            logging.error(f"Chyba při vyhledávání rizika '{risk}': {e}")

    return identified_risks, semanticke_vyhledani

def merge_risks(risks1, risks2):
    """Sloučení dvou seznamů rizik a odstranění duplicit."""
    merged = {}
    for risk in risks1 + risks2:
        source = tuple(risk['source']) if isinstance(risk['source'], list) else risk['source']
        key = (risk['risk'], source)

        if key not in merged:
            merged[key] = risk
        else:
            merged[key]['weight'] += risk['weight']

    return list(merged.values())

def save_report(risks, semanticke_vyhledani, output_path, threshold):
    """Uložení identifikovaných rizik do textového souboru."""
    total_weight = sum(risk.get('weight', 0) for risk in risks)
    recommendation = "Nedoporučujeme podepsat dokument." if total_weight >= threshold else "Doporučujeme dokument podepsat."

    with open(output_path, 'w', encoding='utf-8') as f:
        if not risks and not semanticke_vyhledani:
            f.write("Rizika nebyla nalezena.\n")
            f.write("\nDoporučení: Dokument je bezpečný k podepsání.\n")
            return

        # Sekce přesného shodování klíčových slov
        if risks:
            f.write("Objevená rizika v smlouvě pomocí přesného shodování klíčových slov:\n")
            f.write("=" * 50 + "\n")
            for risk in risks:
                f.write(f"Název rizika: {risk.get('risk', 'Neznámé riziko')}\n")
                f.write(f"Popis: {risk.get('description', 'Bez popisu')}\n")
                f.write(f"Váha: {risk.get('weight', 'Neznámá váha')}\n")
                f.write(f"Typ detekce: {risk.get('type', 'Neznámý typ')}\n")
                f.write(f"Paragraf: {risk.get('source', 'Neznámý paragraf')}\n")
                f.write("-" * 50 + "\n")

        # Sekce semantického vyhledávání
        if semanticke_vyhledani:
            f.write("\nObjevená rizika v smlouvě pomocí semantického vyhledávání:\n")
            f.write("=" * 50 + "\n")
            for item in semanticke_vyhledani:
                f.write(f"Otázka: {item['question']}\n")
                f.write(f"Odpověď: {item['answer']}\n")
                f.write("-" * 50 + "\n")

        f.write(f"\nCelková váha rizik: {total_weight}\n")
        f.write(f"Prahová hodnota: {threshold}\n")
        f.write(f"Doporučení: {recommendation}\n")

def main():
    # Extrakce textu ze smlouvy
    logging.info("Načítání smlouvy...")
    contract_text = extract_text_from_pdf(PDF_PATH)
    if not contract_text:
        logging.error("Nepodařilo se extrahovat text ze smlouvy.")
        return

    # Rozdělení textu na paragrafy
    logging.info("Rozdělování textu na paragrafy...")
    paragraphs = split_text_into_paragraphs(contract_text)
    if not paragraphs:
        logging.warning("Text nebyl rozdělen na paragrafy.")
        return

    # Vytvoření vektorového uložiště
    logging.info("Vytváření vektorového uložiště...")
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    vectorstore = create_vector_store(paragraphs, embeddings)
    if vectorstore is None:
        logging.error("Vektorové uložiště nebylo vytvořeno.")
        return

    # Identifikace rizik přesným shodováním klíčových slov
    logging.info("Identifikace rizik pomocí přesného shodování klíčových slov...")
    rizika_presne = strict_keyword_matching(paragraphs, RISK_FACTORS)

    # Identifikace rizik pomocí semantického vyhledávání
    logging.info("Identifikace rizik pomocí semantického vyhledávání...")
    llm = OpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.0, max_tokens=500)
    rizika_semanticke, semanticke_vyhledani = semantic_search(paragraphs, vectorstore, RISK_FACTORS, llm)

    # Sloučení rizik a odstranění duplicit
    logging.info("Sloučení rizik z obou metod a odstranění duplicit...")
    vsechna_rizika = merge_risks(rizika_presne, rizika_semanticke)

    # Uložení výsledků do souboru
    logging.info("Ukládání výsledků analýzy do souboru...")
    save_report(vsechna_rizika, semanticke_vyhledani, OUTPUT_REPORT_PATH, WEIGHT_THRESHOLD)
    logging.info(f"Analýza dokončena. Výsledky jsou uloženy v souboru {OUTPUT_REPORT_PATH}.")


    result = subprocess.run(['pip', 'freeze'], stdout=subprocess.PIPE)


    with open('requirements.txt', 'wb') as f:
        f.write(result.stdout)

if __name__ == "__main__":
    main()
