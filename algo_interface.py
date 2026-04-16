import tkinter as tk
from tkinter import dnd
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
from pathlib import Path
from usaf_algo import find_usaf_score

class ImageProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Processor - Drag & Drop")
        self.root.geometry("500x300")
        
        # Create drop zone
        self.drop_frame = tk.Frame(root, bg="lightblue", relief="ridge", bd=2)
        self.drop_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.label = tk.Label(
            self.drop_frame,
            text="Drag and drop a folder with images here",
            bg="lightblue",
            font=("Arial", 14)
        )
        self.label.pack(expand=True)
        
        # Register drop target
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.drop_handler)
        
        # Status label
        self.status_label = tk.Label(root, text="Ready", fg="green")
        self.status_label.pack(pady=10)
    
    def drop_handler(self, event):
        """Handle dropped folders or images"""
        files = self.parse_dnd_files(event.data)
        
        if not files:
            self.update_status("No valid path", "red")
            return
        
        valid_paths = []
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}

        for path in files:
            if os.path.isdir(path):
                valid_paths.append(path)
            elif os.path.isfile(path) and Path(path).suffix.lower() in image_extensions:
                valid_paths.append(path)

        if not valid_paths:
            self.update_status("Please drop a folder or image file", "red")
            return

        self.update_status("Processing...", "orange")
        for path in valid_paths:
            if os.path.isdir(path):
                self.process_images(path)
            else:
                find_usaf_score(path)

        self.update_status("Processed dropped items successfully", "green")
    
    def parse_dnd_files(self, data):
        """Parse dropped file paths"""
        # Use Tk's list parser so paths containing spaces are handled correctly.
        return [path.strip('{}') for path in self.root.tk.splitlist(data)]
    
    def process_images(self, folder_path):
        """Extract and process images recursively"""
        try:
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}
            image_paths = []

            for root_dir, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    if Path(filename).suffix.lower() in image_extensions:
                        image_paths.append(os.path.join(root_dir, filename))

            if not image_paths:
                self.update_status("No images found in folder", "red")
                return

            # Process with usaf_aglo
            for image_path in image_paths:
                find_usaf_score(image_path)

            self.update_status(f"Processed {len(image_paths)} images successfully", "green")

        except Exception as e:
            self.update_status(f"Error: {str(e)}", "red")
    
    def update_status(self, message, color):
        """Update status label"""
        self.status_label.config(text=message, fg=color)
        self.root.update()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = ImageProcessorApp(root)
    root.mainloop()