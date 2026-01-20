import os
import requests
from dotenv import load_dotenv

load_dotenv()


class NotionClient:
    def __init__(self):
        self.api_key = os.getenv('NOTION_API_KEY')
        self.base_url = 'https://api.notion.com/v1'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json'
        }
    
    def _extract_page_id(self, page_id):
        """Extract and normalize page ID from URL or raw ID."""
        original = page_id
        
        if 'notion.so' in page_id:
            # Extract the UUID from URL (e.g., Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410)
            url_part = page_id.split('/')[-1].split('?')[0]
            parts = url_part.split('-')
            
            # Find the UUID part (should be the last part that's 32 chars)
            uuid_part = None
            for part in reversed(parts):
                if len(part) == 32 and all(c in '0123456789abcdefABCDEF' for c in part):
                    uuid_part = part
                    break
            
            if uuid_part:
                # Format as UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
                formatted = f"{uuid_part[:8]}-{uuid_part[8:12]}-{uuid_part[12:16]}-{uuid_part[16:20]}-{uuid_part[20:]}"
                print(f"Extracted Notion page ID: {formatted} from URL: {original}")
                return formatted
        
        # If already formatted or raw ID, ensure it has dashes
        page_id_clean = str(page_id).replace('-', '')
        if len(page_id_clean) == 32:
            formatted = f"{page_id_clean[:8]}-{page_id_clean[8:12]}-{page_id_clean[12:16]}-{page_id_clean[16:20]}-{page_id_clean[20:]}"
            print(f"Formatted Notion page ID: {formatted}")
            return formatted
        
        print(f"Using page ID as-is: {page_id}")
        return page_id
    
    def get_page_content(self, page_id):
        """Retrieves the metadata of a Notion page."""
        page_id = self._extract_page_id(page_id)
        url = f'{self.base_url}/pages/{page_id}'
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_page_blocks(self, page_id):
        """Retrieves all content blocks from a Notion page."""
        page_id = self._extract_page_id(page_id)
        url = f'{self.base_url}/blocks/{page_id}/children'
        all_blocks = []
        start_cursor = None
        
        while True:
            params = {'start_cursor': start_cursor} if start_cursor else {}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            all_blocks.extend(data.get('results', []))
            
            if not data.get('has_more'):
                break
            start_cursor = data.get('next_cursor')
        
        return all_blocks
    
    def _extract_rich_text(self, block, block_type):
        """Extract plain text from rich_text array in a block."""
        block_data = block.get(block_type, {})
        rich_text = block_data.get('rich_text', [])
        if not rich_text:
            return None
        return ''.join(item.get('plain_text', '') for item in rich_text)
    
    def extract_text_from_blocks(self, blocks):
        """Extracts plain text from Notion blocks."""
        text_content = []
        block_formatters = {
            'paragraph': lambda t: t,
            'heading_1': lambda t: f"# {t}",
            'heading_2': lambda t: f"## {t}",
            'heading_3': lambda t: f"### {t}",
            'bulleted_list_item': lambda t: f"• {t}",
            'numbered_list_item': lambda t: f"• {t}",
            'to_do': lambda t, checked: f"{'✓' if checked else '☐'} {t}"
        }
        
        for block in blocks:
            block_type = block.get('type')
            text = self._extract_rich_text(block, block_type)
            
            if not text:
                continue
            
            if block_type == 'to_do':
                checked = block.get('to_do', {}).get('checked', False)
                formatted = block_formatters[block_type](text, checked)
            elif block_type in block_formatters:
                formatted = block_formatters[block_type](text)
            else:
                formatted = text
            
            text_content.append(formatted)
        
        return '\n'.join(text_content)
    
    def get_page_as_text(self, page_url):
        """Get a Notion page as plain text."""
        blocks = self.get_page_blocks(page_url)
        return self.extract_text_from_blocks(blocks)
