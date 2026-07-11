#!/usr/bin/env python3
"""PDF 텍스트 추출 + 파일명 변경 + extract 저장 (CrossRef API 없이 수동 이름 매핑 사용)"""
import sys, os, re, json, time
from pathlib import Path
try:
    import fitz
except ImportError:
    print("pip install pymupdf"); sys.exit(1)

_VAULT = Path(__file__).parent.parent
PDF_DIR = _VAULT / "ko/pdf"
NOTES_DIR = PDF_DIR / "notes"
EXTRACT_DIR = _VAULT / "extract"

def extract_text(pdf_path, max_pages=30):
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc[:max_pages]:
        text += page.get_text()
    doc.close()
    return text

def extract_doi(text):
    patterns = [
        r'(?:doi|DOI)\s*[:\s]*\s*(10\.\d{4,}/[^\s,;]+)',
        r'(10\.\d{4,}/[^\s,;\]]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).rstrip('.,/?')
    return None

def save_extract(pdf_name, text):
    date_str = time.strftime("%Y-%m-%d")
    out_path = EXTRACT_DIR / f"{date_str}.txt"
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"===== {pdf_name} =====\n\n")
        f.write(text[:50000])
        f.write("\n\n=====\n\n")
    return out_path

def main():
    # Name mapping: source_file -> target_name (without .pdf)
    NAME_MAP = {
        "1-s2.0-S0022282826000921-main.pdf": "Tadokoro2026_JMolCellCardiol",
        "1-s2.0-S014296122600431X-main.pdf": "Wang2026_Biomaterials",
        "1-s2.0-S0168365925006510-main.pdf": "Miyasaki2025_JControlRelease",
        "1-s2.0-S0928098726001703-main.pdf": "Tirpe2026_EurJPharmSci",
        "1-s2.0-S2352320424001706-main.pdf": "Chen2024_RegenTher",
        "1-s2.0-S240547122600133X-main.pdf": "He2026_CellSyst",
        "1-s2.0-S2667237522002089-main.pdf": "Barber2022_CellRepMeth",
        "1471-2121-12-43.pdf": "Dukes2011_BMCCellBiol-review",
        "1562.pdf": "Lo2021_CancerDiscov",
        "2026.06.09.731035v1.full.pdf": "Miyata2026_bioRxiv",
        "2026.06.16.732511v1.full.pdf": "Fankhauser2026_bioRxiv",
        "2026.06.21.729417.full.pdf": "Wasko2026_bioRxiv",
        "2159-8290_cd-20-1109v1.pdf": "dup-Lo2021_CancerDiscov",
        "978-1-59745-000-3.pdf": "Salinas2006_XenopusProtoc",
        "Advanced Science - 2023 - Hu - Oncogenic KRAS  Mucin 4  and Activin A-Mediated Fibroblast Activation Cooperate for PanIN.pdf": "Hu2023_AdvSci",
        "NEJMoa2515131.pdf": "Hou2026_NEJM",
        "NEJMoa2518035.pdf": "Ruella2026_NEJM",
        "NanoLetters_Han.pdf": "Han2024_NanoLett",
        "PIIS0092867425009298.pdf": "Delafiori2025_Cell",
        "PIIS2589004226020122.pdf": "DominguezRomero2026_iScience",
        "PIIS266616672500574X.pdf": "Protocol3DTumor2026_STARProtoc",
        "PIIS2666166726002558.pdf": "Li2026_STARProtoc",
        "PIIS2666379126000819.pdf": "Cai2026_CellRepMed",
        "PIIS2666979X25001314.pdf": "Zhou2025_CellGenom",
        "RNA-2022-Gadkari-1263-78.pdf": "Gadkari2022_RNA",
        "bio062675.pdf": "Andreazzoli2026_Development",
        "bioinformatics_21_6_703.pdf": "Zheng2004_Bioinformatics",
        "bmb-59-6-321.pdf": "Yang2026_BMBRep",
        "cd-22-1467.pdf": "Hsu2022_CancerDiscov",
        "d41586-025-03450-5.pdf": "NatureNews2025_Nature",
        "elife-109518-v1.pdf": "Lin2026_eLife",
        "fcell-11-1245296.pdf": "Shigemura2023_FrontCellDevBiol",
        "freed-mezger-freed-1970-stable-haploid-cultured-cell-lines-from-frog-embryos_.pdf": "Freed1970_PNAS",
        "gkag578.pdf": "Kunwar2026_NucleicAcidsRes",
        "heijo-et-al-2020-dna-content-contributes-to-nuclear-size-control-in-xenopus-laevis.pdf": "Heijo2020_MolBiolCell",
        "iyag140.pdf": "Ogbunugafor2026_Genetics",
        "iyag149.pdf": "Schacherer2026_Genetics",
        "jkae176.pdf": "Correia2026_G3",
        "journal.pbio.3003865.pdf": "DocampoSeara2026_PLoSBiol",
        "lever-1979-inducers-of-mammalian-cell-differentiation-stimulate-dome-formation-in-a-differentiated-kidney-epithelial.pdf": "Lever1979_PNAS",
        "msag147.pdf": "Osterhof2026_MolBiolEvol",
        "optimizing-peptide-conjugated-lipid-nanoparticles-for-efficient-sirna-delivery-across-the-blood-brain-barrier-and.pdf": "Tong2025_ACSChemBiol",
        "s11033-023-08380-x.pdf": "Pung2023_MolBiolRep-review",
        "s12964-026-03006-8_reference.pdf": "Prasai2026_CellCommunSignal",
        "s13059-020-01956-x.pdf": "Cui2020_GenomeBiol",
        "s13059-026-04031-z.pdf": "Chaudhary2026_GenomeBiol",
        "s13059-026-04150-7_reference.pdf": "Smith2026_GenomeBiol",
        "s41378-024-00861-8.pdf": "Chen2025_MicrosystemsNanoeng",
        "s41392-026-02798-y.pdf": "Lisle2026_SignalTransductTargetTher",
        "s41419-025-08101-1.pdf": "Tian2025_CellDeathDis-review",
        "s41467-024-50698-y.pdf": "Ding2024_NatCommun",
        "s41467-024-55399-0.pdf": "Landwehr2024_NatCommun",
        "s41467-025-67749-7.pdf": "Jun2025_NatCommun",
        "s41467-026-74520-z_reference.pdf": "Yu2026_NatCommun",
        "s41586-024-07234-1.pdf": "Mannens2025_Nature",
        "s41586-026-10792-1_reference.pdf": "Bower2026_Nature",
        "s41587-023-01964-9.pdf": "Yao2024_NatBiotechnol",
        "s41587-024-02437-3.pdf": "Chen2025b_NatBiotechnol",
        "s41587-026-03221-1.pdf": "PublisherCorrection2026_NatBiotechnol",
        "s41588-022-01088-x.pdf": "Becker2022_NatGenet",
        "s41592-020-0837-5.pdf": "Schraivogel2020_NatMethods",
        "s41592-024-02586-y.pdf": "Li2025b_NatMethods",
        "s41592-025-02657-8.pdf": "Kida2025_NatMethods",
        "s41592-025-02700-8.pdf": "LobatoMoreno2025_NatMethods",
        "s41596-025-01310-0.pdf": "Yildiz2025_NatProtoc",
        "s41929-022-00909-w.pdf": "Yu2023_NatCatal-review",
        "sciadv.abd9858.pdf": "Nims2021_SciAdv",
        "sciadv.abk0133.pdf": "Liu2022_SciAdv",
        "sciadv.add4623.pdf": "HerreraBarrera2023_SciAdv",
        "sciadv.ady7359.pdf": "Huang2026_SciAdv",
        "science.adq2084.pdf": "Gandin2025_Science",
        "science.adz4351.pdf": "Huang2026_Science",
        "zucchi-et-al-2002-dome-formation-in-cell-cultures-as-expression-of-an-early-stage-of-lactogenic-differentiation-of-the.pdf": "Zucchi2002_MolCellEndocrinol",
    }

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        if pdf_name.startswith("Tran2026_Science"):
            print(f"[SKIP] {pdf_name} (already processed)")
            continue

        target_stem = NAME_MAP.get(pdf_name)
        if not target_stem:
            print(f"[SKIP] {pdf_name} (no name mapping)")
            continue

        if target_stem.startswith("dup-"):
            print(f"[SKIP] {pdf_name} (duplicate of {target_stem.replace('dup-','')})")
            continue
        if target_stem.startswith("PublisherCorrection"):
            print(f"[SKIP] {pdf_name} (publisher correction, not primary article)")
            continue
        if target_stem.startswith("Protocol3DTumor"):
            print(f"[SKIP] {pdf_name} (protocol, need author lookup)")
            continue
        if target_stem.startswith("NatureNews"):
            print(f"[SKIP] {pdf_name} (nature news article)")
            continue

        is_review = "-review" in target_stem
        is_dup = target_stem.startswith("dup-")

        print(f"\n[PROCESS] {pdf_name} -> {target_stem}.pdf")

        t0 = time.time()
        text = extract_text(pdf_path)
        t1 = time.time()
        print(f"   텍스트 추출: {len(text):,} chars ({t1-t0:.1f}s)")

        # Save to extract/
        extract_path = save_extract(pdf_name, text)
        print(f"   추출 저장: {extract_path.name}")

        # Save extracted text to notes/
        notes_path = NOTES_DIR / f"{target_stem}_extracted.txt"
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write(text[:50000])
        print(f"   노트 저장: {notes_path.name}")

        # Rename PDF
        target_path = PDF_DIR / f"{target_stem}.pdf"
        if target_path.exists():
            print(f"   [WARN] 대상 파일 이미 존재: {target_stem}.pdf")
        else:
            pdf_path.rename(target_path)
            print(f"   이름 변경: {pdf_name} -> {target_stem}.pdf")

    print("\n[DONE] All processing complete")

if __name__ == "__main__":
    main()
