import os
import logging
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader

logger = logging.getLogger("DocumentGenerator")

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "bank_templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "generated_docs")

# Ensure output dir exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

class DocumentGenerator:
    def __init__(self):
        try:
            self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        except Exception as e:
            logger.error(f"Failed to load templates from {TEMPLATE_DIR}: {e}")
            self.env = None

    def generate(self, case, template_name: str) -> str:
        """
        Generates a document based on the case context and template.
        Returns the path to the generated file.
        """
        if not self.env:
            raise RuntimeError("Template environment not initialized.")

        try:
            template = self.env.get_template(template_name)
            
            # Render context mapping
            rendered_content = template.render(
                case=case,
                date=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            )
            
            output_filename = f"{case.application_id}_{template_name.replace('.md', '.txt')}"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)
                
            logger.info(f"Generated document saved to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating document {template_name}: {e}")
            raise

# Singleton instance
document_generator = DocumentGenerator()
