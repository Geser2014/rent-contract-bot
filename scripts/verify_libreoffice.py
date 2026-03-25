import subprocess
import os
from pathlib import Path

def find_libreoffice_windows():
    """Find LibreOffice on Windows"""
    possible_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def verify_libreoffice():
    """Verify LibreOffice installation"""
    print("Searching for LibreOffice...")
    
    # Find soffice
    soffice_path = find_libreoffice_windows()
    
    if not soffice_path:
        print("❌ LibreOffice not found!")
        print("Please install LibreOffice from https://www.libreoffice.org/download/")
        return False
    
    print(f"✅ LibreOffice found at: {soffice_path}")
    
    # Test conversion
    print("Testing DOCX → PDF conversion...")
    
    try:
        from docx import Document
        
        # Create test DOCX
        test_dir = Path("temp_test")
        test_dir.mkdir(exist_ok=True)
        
        doc = Document()
        doc.add_paragraph("Test document")
        test_docx = test_dir / "test.docx"
        doc.save(str(test_docx))
        
        # Convert to PDF
        result = subprocess.run(
            [
                soffice_path,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(test_dir),
                str(test_docx)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        test_pdf = test_dir / "test.pdf"
        
        if test_pdf.exists():
            print("✅ Conversion successful!")
            # Cleanup
            import shutil
            shutil.rmtree(test_dir)
            return True
        else:
            print("❌ Conversion failed!")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = verify_libreoffice()
    exit(0 if success else 1)