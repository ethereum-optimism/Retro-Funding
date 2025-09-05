import argparse
import os
import sys
import pandas as pd
import requests
from PIL import Image
from io import BytesIO
import time
from typing import Optional, Dict
from dotenv import load_dotenv
from pyoso import Client


class LogoManager:
    """
    Unified utility for managing atlas project logos.
    Handles database queries, image downloading, and file management.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the LogoManager.
        
        Args:
            output_dir: Output directory for logos (default: results/logos/)
        """
        if output_dir is None:
            # Use project root to create results/logos/ directory
            current_file = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_file, '../../..'))
            output_dir = os.path.join(project_root, 'results', 'logos')
        
        self.output_dir = output_dir
        self.csv_path = os.path.join(output_dir, 'atlas_logos.csv')
        self.client = self._init_oso_client()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    def _init_oso_client(self) -> Client:
        """Initialize the OSO client with API key from environment."""
        load_dotenv()
        api_key = os.environ.get('OSO_API_KEY')
        if not api_key:
            raise ValueError("OSO_API_KEY environment variable not set")
        return Client(api_key=api_key)
    
    def generate_logos_data(self) -> pd.DataFrame:
        """
        Execute the atlas application query to get project logos and metadata.
        
        Returns:
            DataFrame with atlas project data including logos and metadata
        """
        query = """
        SELECT
          a.atlas_id,
          p.display_name,
          p.thumbnail_url,
          p.twitter_url,
          a.round_id,
          a.created_at,
          p.updated_at
        FROM stg_op_atlas_application AS a
        JOIN stg_op_atlas_project AS p
          ON a.atlas_id = p.atlas_id
        WHERE
          a.round_id IN ('7','8')
          AND a.status = 'submitted'
          AND a.created_at >= DATE('2025-02-01')
        ORDER BY created_at
        """
        
        print("Executing atlas application query...")
        df = self.client.to_pandas(query)
        
        # Format datetime columns
        df['updated_at'] = pd.to_datetime(df['updated_at'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['updated_at'] = df['updated_at'].dt.strftime('%Y-%m-%d')
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d')
        
        print(f"✓ Retrieved {len(df)} atlas applications")
        return df
    
    def save_logos_data(self, df: pd.DataFrame) -> None:
        """Save the logos data to CSV file."""
        df.to_csv(self.csv_path, index=False)
        print(f"✓ Saved logos data to {self.csv_path}")
    
    def load_logos_data(self) -> pd.DataFrame:
        """Load logos data from CSV file."""
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        df = pd.read_csv(self.csv_path)
        print(f"Loaded {len(df)} records from {self.csv_path}")
        return df
    
    def get_existing_images(self) -> set:
        """Get set of atlas_ids for which images already exist."""
        existing_images = set()
        if os.path.exists(self.output_dir):
            for filename in os.listdir(self.output_dir):
                if filename.endswith('.jpg') and filename.startswith('0x'):
                    existing_images.add(filename[:-4])  # Remove .jpg extension
        
        print(f"Found {len(existing_images)} existing images")
        return existing_images
    
    def download_image(self, url: str, timeout: int = 30) -> Optional[bytes]:
        """Download an image from a URL."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"  ✗ Failed to download {url}: {str(e)}")
            return None
    
    def resize_image(self, image_bytes: bytes, target_size: tuple = (1000, 1000)) -> Optional[Image.Image]:
        """Resize an image to target size while maintaining aspect ratio."""
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize while maintaining aspect ratio
            image.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # Create centered image with target size
            new_image = Image.new('RGB', target_size, (255, 255, 255))
            x_offset = (target_size[0] - image.size[0]) // 2
            y_offset = (target_size[1] - image.size[1]) // 2
            new_image.paste(image, (x_offset, y_offset))
            
            return new_image
        except Exception as e:
            print(f"  ✗ Failed to resize image: {str(e)}")
            return None
    
    def get_filename_from_atlas_id(self, atlas_id: str) -> str:
        """Generate filename from atlas_id."""
        safe_filename = atlas_id.replace('/', '_').replace('\\', '_')
        return f"{safe_filename}.jpg"
    
    def download_and_resize_logos(self, df: pd.DataFrame, refresh_all: bool = False, delay: float = 0.5) -> Dict[str, int]:
        """Download and resize logo images from the DataFrame."""
        # Filter out rows without thumbnail URLs
        df_with_urls = df[df['thumbnail_url'].notna() & (df['thumbnail_url'] != '')]
        print(f"Found {len(df_with_urls)} records with thumbnail URLs")
        
        if len(df_with_urls) == 0:
            print("No thumbnail URLs found in the data")
            return {'successful': 0, 'failed': 0, 'skipped': 0}
        
        # Get existing images if not refreshing all
        existing_images = set() if refresh_all else self.get_existing_images()
        
        # Download and process images
        successful_downloads = 0
        failed_downloads = 0
        skipped_downloads = 0
        
        for idx, row in df_with_urls.iterrows():
            atlas_id = row['atlas_id']
            display_name = row['display_name']
            thumbnail_url = row['thumbnail_url']
            
            # Skip if image already exists and not refreshing
            if atlas_id in existing_images and not refresh_all:
                print(f"[{idx + 1}/{len(df_with_urls)}] Skipping: {display_name} (already exists)")
                skipped_downloads += 1
                continue
            
            print(f"[{idx + 1}/{len(df_with_urls)}] Processing: {display_name}")
            
            # Download image
            image_bytes = self.download_image(thumbnail_url)
            if image_bytes is None:
                failed_downloads += 1
                continue
            
            # Resize image
            resized_image = self.resize_image(image_bytes)
            if resized_image is None:
                failed_downloads += 1
                continue
            
            # Generate filename and save
            filename = self.get_filename_from_atlas_id(atlas_id)
            output_path = os.path.join(self.output_dir, filename)
            
            try:
                resized_image.save(output_path, 'JPEG', quality=95)
                print(f"  ✓ Saved: {filename}")
                successful_downloads += 1
            except Exception as e:
                print(f"  ✗ Failed to save {filename}: {str(e)}")
                failed_downloads += 1
            
            # Add delay between downloads to be respectful
            if delay > 0:
                time.sleep(delay)
        
        return {
            'successful': successful_downloads,
            'failed': failed_downloads,
            'skipped': skipped_downloads
        }
    
    def run_full_workflow(self, refresh_all: bool = False, delay: float = 0.5) -> None:
        """Run the complete workflow: query database, save CSV, and download images."""
        print("=== Atlas Logo Manager ===")
        
        # Step 1: Generate/update CSV data
        print("\n1. Fetching atlas data from database...")
        df = self.generate_logos_data()
        self.save_logos_data(df)
        
        # Step 2: Download images
        print(f"\n2. Downloading logo images...")
        stats = self.download_and_resize_logos(df, refresh_all, delay)
        
        # Step 3: Summary
        print(f"\n=== Download Summary ===")
        print(f"  ✓ Successful: {stats['successful']}")
        print(f"  ✗ Failed: {stats['failed']}")
        print(f"  ⏭️  Skipped: {stats['skipped']}")
        print(f"  📁 Images saved to: {self.output_dir}")
        print(f"  📄 CSV data saved to: {self.csv_path}")
    
    def run_download_only(self, refresh_all: bool = False, delay: float = 0.5) -> None:
        """Run only the download process using existing CSV data."""
        print("=== Atlas Logo Downloader ===")
        
        # Load existing CSV data
        print("\n1. Loading existing CSV data...")
        df = self.load_logos_data()
        
        # Download images
        print(f"\n2. Downloading logo images...")
        stats = self.download_and_resize_logos(df, refresh_all, delay)
        
        # Summary
        print(f"\n=== Download Summary ===")
        print(f"  ✓ Successful: {stats['successful']}")
        print(f"  ✗ Failed: {stats['failed']}")
        print(f"  ⏭️  Skipped: {stats['skipped']}")
        print(f"  📁 Images saved to: {self.output_dir}")


def main():
    """Main function for the logo manager CLI."""
    parser = argparse.ArgumentParser(description='Atlas Logo Manager - Query database and manage logo images')
    parser.add_argument('--output-dir', '-o', type=str,
                       help='Output directory for CSV and images (default: results/logos/)')
    parser.add_argument('--refresh-all', '-r', action='store_true',
                       help='Download all images even if they already exist')
    parser.add_argument('--delay', '-d', type=float, default=0.5,
                       help='Delay between downloads in seconds (default: 0.5)')
    parser.add_argument('--download-only', action='store_true',
                       help='Only download images using existing CSV data (skip database query)')
    
    args = parser.parse_args()
    
    try:
        manager = LogoManager(args.output_dir)
        
        if args.download_only:
            manager.run_download_only(args.refresh_all, args.delay)
        else:
            manager.run_full_workflow(args.refresh_all, args.delay)
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
