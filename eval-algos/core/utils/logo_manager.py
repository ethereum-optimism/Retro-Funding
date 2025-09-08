import argparse
import os
import sys
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageOps
from io import BytesIO
import time
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv
from pyoso import Client

# Constants
TARGET_SIZE = (1000, 1000)
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
DEFAULT_DELAY = 0.5
JPEG_QUALITY = 95
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB cap

# Safe filename pattern
SAFE_NAME_PATTERN = re.compile(r'[^a-zA-Z0-9._-]')


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe."""
    return SAFE_NAME_PATTERN.sub('_', filename or '')


def make_session() -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.mount('http://', HTTPAdapter(max_retries=retry))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return session


class LogoManager:
    """
    Unified utility for managing atlas project logos.
    Handles database queries, image downloading, and file management.
    """
    
    def __init__(self, client: Client, output_dir: Path = None):
        """
        Initialize the LogoManager.
        
        Args:
            client: OSO client instance
            output_dir: Output directory for logos (default: results/logos/)
        """
        if output_dir is None:
            # Use project root to create results/logos/ directory
            current_file = Path(__file__).parent
            project_root = current_file.parent.parent.parent
            output_dir = project_root / 'results' / 'logos'
        
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / 'raw'
        self.processed_dir = self.output_dir / 'processed'
        self.csv_path = self.output_dir / 'atlas_logos.csv'
        self.client = client
        
        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
    
    
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
    
    def get_existing_images(self, processed: bool = False) -> set:
        """Get set of atlas_ids for which images already exist."""
        target_dir = self.processed_dir if processed else self.raw_dir
        existing_images = set()
        
        if target_dir.exists():
            for file_path in target_dir.iterdir():
                if file_path.is_file():
                    if processed and file_path.suffix.lower() == '.jpg':
                        existing_images.add(file_path.stem)
                    elif not processed and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                        existing_images.add(file_path.stem)
        
        logging.info(f"Found {len(existing_images)} existing {'processed' if processed else 'raw'} images")
        return existing_images
    
    def download_image(self, session: requests.Session, url: str, timeout: int = 20) -> Optional[bytes]:
        """Download an image from a URL with content-type validation."""
        try:
            if not url or not url.startswith(('http://', 'https://')):
                logging.warning(f"Invalid URL: {url}")
                return None
            
            with session.get(url, timeout=timeout, stream=True) as response:
                response.raise_for_status()
                
                # Validate content type
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    logging.warning(f"Invalid content type '{content_type}' for {url}")
                    return None
                
                # Stream and cap size
                chunks = []
                total_size = 0
                for chunk in response.iter_content(8192):
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_IMAGE_SIZE:
                        logging.warning(f"Image too large ({total_size} bytes) for {url}")
                        return None
                    chunks.append(chunk)
                
                return b''.join(chunks)
        except Exception as e:
            logging.error(f"Failed to download {url}: {str(e)}")
            return None
    
    def save_raw_image(self, image_bytes: bytes, atlas_id: str) -> bool:
        """Save raw image bytes to file."""
        try:
            # Determine file extension from image content
            image = Image.open(BytesIO(image_bytes))
            format_ext = image.format.lower() if image.format else 'jpg'
            if format_ext == 'jpeg':
                format_ext = 'jpg'
            
            safe_filename = sanitize_filename(atlas_id)
            output_path = self.raw_dir / f"{safe_filename}.{format_ext}"
            
            output_path.write_bytes(image_bytes)
            logging.info(f"Saved raw: {output_path.name}")
            return True
        except Exception as e:
            logging.error(f"Failed to save raw image: {str(e)}")
            return False
    
    def resize_image(self, image_bytes: bytes, target_size: tuple = TARGET_SIZE) -> Optional[Image.Image]:
        """Resize an image to target size using center-based cropping."""
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Use ImageOps.fit for simpler, more reliable center-crop and resize
            return ImageOps.fit(
                image, 
                target_size, 
                method=Image.Resampling.LANCZOS, 
                centering=(0.5, 0.5)
            )
        except Exception as e:
            logging.error(f"Failed to resize image: {str(e)}")
            return None
    
    def get_filename_from_atlas_id(self, atlas_id: str) -> str:
        """Generate filename from atlas_id."""
        safe_filename = sanitize_filename(atlas_id)
        return f"{safe_filename}.jpg"
    
    def _empty_stats(self) -> Dict[str, int]:
        """Return empty statistics dictionary."""
        return {'successful': 0, 'failed': 0, 'skipped': 0}
    
    def _print_summary(self, stats: Dict[str, int], title: str, output_dir: str, csv_path: str = None) -> None:
        """Print processing summary."""
        logging.info(f"=== {title} ===")
        logging.info(f"  ✓ Successful: {stats['successful']}")
        logging.info(f"  ✗ Failed: {stats['failed']}")
        logging.info(f"  ⏭️  Skipped: {stats['skipped']}")
        logging.info(f"  📁 Images saved to: {output_dir}")
        if csv_path:
            logging.info(f"  📄 CSV data saved to: {csv_path}")
    
    def process_raw_images(self, input_dir: Path = None, output_dir: Path = None, overwrite: bool = False) -> Dict[str, int]:
        """
        Process raw logo images in a directory to 1000x1000px with center-based cropping.
        
        Args:
            input_dir: Directory containing raw logo images (default: self.raw_dir)
            output_dir: Directory to save processed images (default: self.processed_dir)
            overwrite: If True, overwrite existing processed images
            
        Returns:
            Dictionary with processing statistics
        """
        if input_dir is None:
            input_dir = self.raw_dir
        
        if output_dir is None:
            output_dir = self.processed_dir
        
        output_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Input directory: {input_dir}")
        logging.info(f"Output directory: {output_dir}")
        
        successful_processed = 0
        failed_processed = 0
        skipped_processed = 0
        
        # Find all image files
        image_files = [f for f in input_dir.iterdir() 
                      if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
        total_files = len(image_files)
        
        if total_files == 0:
            logging.warning("No image files found in the input directory.")
            return self._empty_stats()
        
        logging.info(f"Found {total_files} image files to process.")
        
        for idx, input_path in enumerate(image_files, 1):
            output_filename = f"{input_path.stem}.jpg"  # Always save as JPG
            output_path = output_dir / output_filename
            
            if output_path.exists() and not overwrite:
                logging.info(f"[{idx}/{total_files}] Skipping: {input_path.name} (already processed)")
                skipped_processed += 1
                continue
            
            logging.info(f"[{idx}/{total_files}] Processing: {input_path.name}")
            
            try:
                # Read image file
                image_bytes = input_path.read_bytes()
                
                # Process image
                resized_image = self.resize_image(image_bytes)
                
                if resized_image is None:
                    failed_processed += 1
                    continue
                
                # Save processed image
                resized_image.save(output_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                logging.info(f"  ✓ Saved: {output_filename}")
                successful_processed += 1
                
            except Exception as e:
                logging.error(f"  ✗ Failed to process {input_path.name}: {str(e)}")
                failed_processed += 1
        
        return {
            'successful': successful_processed,
            'failed': failed_processed,
            'skipped': skipped_processed
        }
    
    def _process_single_image(self, image_bytes: bytes, atlas_id: str, raw_only: bool = False) -> bool:
        """Process a single image (save raw or resize and save)."""
        if raw_only:
            return self.save_raw_image(image_bytes, atlas_id)
        else:
            resized_image = self.resize_image(image_bytes)
            if resized_image is None:
                return False
            
            filename = self.get_filename_from_atlas_id(atlas_id)
            output_path = self.processed_dir / filename
            
            try:
                resized_image.save(output_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                logging.info(f"  ✓ Saved: {filename}")
                return True
            except Exception as e:
                logging.error(f"  ✗ Failed to save {filename}: {str(e)}")
                return False
    
    def download_logos(self, df: pd.DataFrame, refresh_all: bool = False, delay: float = DEFAULT_DELAY, raw_only: bool = False) -> Dict[str, int]:
        """Download logo images from the DataFrame (raw or processed)."""
        # Filter out rows without thumbnail URLs
        df_with_urls = df[df['thumbnail_url'].notna() & (df['thumbnail_url'] != '')]
        logging.info(f"Found {len(df_with_urls)} records with thumbnail URLs")
        
        if len(df_with_urls) == 0:
            logging.warning("No thumbnail URLs found in the data")
            return self._empty_stats()
        
        # Get existing images if not refreshing all - FIXED: use correct directory based on mode
        existing_images = set() if refresh_all else self.get_existing_images(processed=not raw_only)
        
        # Create session for better performance
        session = make_session()
        
        # Download images
        stats = {'successful': 0, 'failed': 0, 'skipped': 0}
        action = "Downloading" if raw_only else "Processing"
        
        for idx, row in df_with_urls.iterrows():
            atlas_id = row['atlas_id']
            display_name = row['display_name']
            thumbnail_url = row['thumbnail_url']
            
            # Skip if image already exists and not refreshing
            if atlas_id in existing_images and not refresh_all:
                logging.info(f"[{idx + 1}/{len(df_with_urls)}] Skipping: {display_name} (already exists)")
                stats['skipped'] += 1
                continue
            
            logging.info(f"[{idx + 1}/{len(df_with_urls)}] {action}: {display_name}")
            
            # Download and process image
            image_bytes = self.download_image(session, thumbnail_url)
            if image_bytes is None:
                stats['failed'] += 1
                continue
            
            if self._process_single_image(image_bytes, atlas_id, raw_only):
                stats['successful'] += 1
            else:
                stats['failed'] += 1
            
            # Add delay between downloads
            if delay > 0:
                time.sleep(delay)
        
        return stats
    
    def run_full_workflow(self, refresh_all: bool = False, delay: float = DEFAULT_DELAY, raw_only: bool = False) -> None:
        """Run the complete workflow: query database, save CSV, and download images."""
        logging.info("=== Atlas Logo Manager ===")
        
        # Step 1: Generate/update CSV data
        logging.info("1. Fetching atlas data from database...")
        df = self.generate_logos_data()
        self.save_logos_data(df)
        
        # Step 2: Download images
        action = "Downloading raw logo images" if raw_only else "Downloading and processing logo images"
        logging.info(f"2. {action}...")
        stats = self.download_logos(df, refresh_all, delay, raw_only)
        
        # Step 3: Summary
        self._print_summary(stats, "Download Summary", str(self.output_dir), str(self.csv_path))
    
    def run_download_only(self, refresh_all: bool = False, delay: float = DEFAULT_DELAY, raw_only: bool = False) -> None:
        """Run only the download process using existing CSV data."""
        logging.info("=== Atlas Logo Downloader ===")
        
        # Load existing CSV data
        logging.info("1. Loading existing CSV data...")
        df = self.load_logos_data()
        
        # Download images
        action = "Downloading raw logo images" if raw_only else "Downloading and processing logo images"
        logging.info(f"2. {action}...")
        stats = self.download_logos(df, refresh_all, delay, raw_only)
        
        # Summary
        self._print_summary(stats, "Download Summary", str(self.output_dir))
    
    def create_filtered_folders(self, consolidated_rewards_path: str) -> None:
        """
        Create three filtered folders based on consolidated rewards data:
        1. All projects with rewards > 0
        2. Unique onchain builder projects with rewards > 0
        3. Unique devtooling projects with rewards > 0
        
        Args:
            consolidated_rewards_path: Path to the consolidated rewards CSV file
        """
        logging.info("=== Creating Filtered Logo Folders ===")
        
        # Load consolidated rewards data
        logging.info(f"1. Loading consolidated rewards from {consolidated_rewards_path}")
        rewards_df = pd.read_csv(consolidated_rewards_path)
        
        # Filter projects with rewards > 0
        rewards_df = rewards_df[rewards_df['op_reward'] > 0]
        logging.info(f"   Found {len(rewards_df)} reward entries with rewards > 0")
        
        # Create filtered directories
        all_rewards_dir = self.output_dir / 'filtered_all_rewards'
        onchain_rewards_dir = self.output_dir / 'filtered_onchain_rewards'
        devtooling_rewards_dir = self.output_dir / 'filtered_devtooling_rewards'
        
        for dir_path in [all_rewards_dir, onchain_rewards_dir, devtooling_rewards_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Get all unique atlas_ids with rewards > 0
        all_rewarded_ids = set(rewards_df['op_atlas_id'].unique())
        logging.info(f"   Found {len(all_rewarded_ids)} unique projects with rewards > 0")
        
        # Copy logos for all projects with rewards > 0
        logging.info("2. Creating folder with all projects that have rewards > 0...")
        all_copied = self._copy_logos_to_folder(all_rewarded_ids, all_rewards_dir)
        
        # Filter for onchain builder projects
        onchain_df = rewards_df[rewards_df['filename'].str.contains('onchain', na=False)]
        onchain_rewarded_ids = set(onchain_df['op_atlas_id'].unique())
        logging.info(f"   Found {len(onchain_rewarded_ids)} unique onchain builder projects with rewards > 0")
        
        # Copy logos for onchain builder projects
        logging.info("3. Creating folder with onchain builder projects that have rewards > 0...")
        onchain_copied = self._copy_logos_to_folder(onchain_rewarded_ids, onchain_rewards_dir)
        
        # Filter for devtooling projects
        devtooling_df = rewards_df[rewards_df['filename'].str.contains('devtooling', na=False)]
        devtooling_rewarded_ids = set(devtooling_df['op_atlas_id'].unique())
        logging.info(f"   Found {len(devtooling_rewarded_ids)} unique devtooling projects with rewards > 0")
        
        # Copy logos for devtooling projects
        logging.info("4. Creating folder with devtooling projects that have rewards > 0...")
        devtooling_copied = self._copy_logos_to_folder(devtooling_rewarded_ids, devtooling_rewards_dir)
        
        # Summary
        logging.info("=== Filtered Folders Summary ===")
        logging.info(f"  📁 All rewards folder: {all_copied} logos copied to {all_rewards_dir}")
        logging.info(f"  📁 Onchain rewards folder: {onchain_copied} logos copied to {onchain_rewards_dir}")
        logging.info(f"  📁 Devtooling rewards folder: {devtooling_copied} logos copied to {devtooling_rewards_dir}")
    
    def _copy_logos_to_folder(self, atlas_ids: set, target_dir: Path) -> int:
        """
        Copy processed logos for given atlas_ids to target directory.
        
        Args:
            atlas_ids: Set of atlas_ids to copy logos for
            target_dir: Target directory to copy logos to
            
        Returns:
            Number of logos successfully copied
        """
        copied_count = 0
        
        for atlas_id in atlas_ids:
            source_path = self.processed_dir / f"{atlas_id}.jpg"
            target_path = target_dir / f"{atlas_id}.jpg"
            
            if source_path.exists():
                try:
                    # Copy the file
                    import shutil
                    shutil.copy2(source_path, target_path)
                    copied_count += 1
                except Exception as e:
                    logging.warning(f"Failed to copy {atlas_id}.jpg: {str(e)}")
            else:
                logging.warning(f"Logo not found for atlas_id: {atlas_id}")
        
        return copied_count


def main():
    """Main function for the logo manager CLI."""
    parser = argparse.ArgumentParser(description='Atlas Logo Manager - Query database and manage logo images')
    parser.add_argument('--output-dir', '-o', type=Path,
                       help='Output directory for CSV and images (default: results/logos/)')
    parser.add_argument('--refresh-all', '-r', action='store_true',
                       help='Download all images even if they already exist')
    parser.add_argument('--delay', '-d', type=float, default=DEFAULT_DELAY,
                       help=f'Delay between downloads in seconds (default: {DEFAULT_DELAY})')
    parser.add_argument('--download-only', action='store_true',
                       help='Only download images using existing CSV data (skip database query)')
    parser.add_argument('--raw-only', action='store_true',
                       help='Download raw images without resizing (preserves original format and dimensions)')
    parser.add_argument('--process-only', action='store_true',
                       help='Only process existing raw images to 1000x1000px (skip download)')
    parser.add_argument('--input-dir', '-i', type=Path,
                       help='Input directory for processing (used with --process-only)')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing processed images (used with --process-only)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress output except errors')
    parser.add_argument('--create-filtered-folders', action='store_true',
                       help='Create filtered folders based on consolidated rewards data')
    parser.add_argument('--rewards-file', type=str,
                       help='Path to consolidated rewards CSV file (required with --create-filtered-folders)')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else (logging.ERROR if args.quiet else logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    try:
        # Initialize OSO client
        load_dotenv()
        api_key = os.environ.get('OSO_API_KEY')
        if not api_key:
            raise ValueError("OSO_API_KEY environment variable not set")
        client = Client(api_key=api_key)
        
        # Create manager with dependency injection
        manager = LogoManager(client, args.output_dir)
        
        if args.create_filtered_folders:
            # Create filtered folders based on rewards data
            if not args.rewards_file:
                raise ValueError("--rewards-file is required when using --create-filtered-folders")
            manager.create_filtered_folders(args.rewards_file)
        elif args.process_only:
            # Process existing raw images
            input_dir = args.input_dir if args.input_dir else manager.raw_dir
            stats = manager.process_raw_images(input_dir, overwrite=args.overwrite)
            
            manager._print_summary(stats, "Processing Summary", str(manager.processed_dir))
        elif args.download_only:
            manager.run_download_only(args.refresh_all, args.delay, args.raw_only)
        else:
            manager.run_full_workflow(args.refresh_all, args.delay, args.raw_only)
        
    except KeyboardInterrupt:
        logging.info("Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
