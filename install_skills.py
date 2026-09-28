#!/usr/bin/env python3
import os
import sys
import argparse

def install_skills(source_dir, target_dir, overwrite=False):
    if not os.path.isdir(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)
        
    os.makedirs(target_dir, exist_ok=True)
    
    for skill_name in os.listdir(source_dir):
        skill_source = os.path.join(source_dir, skill_name)
        if not os.path.isdir(skill_source):
            continue
            
        skill_target = os.path.join(target_dir, skill_name)
        
        # Validated state check can be implemented here in the future
        # For now we create a symlink directly from source to runtime
        
        if os.path.exists(skill_target) or os.path.islink(skill_target):
            if overwrite:
                if os.path.islink(skill_target):
                    os.unlink(skill_target)
                else:
                    print(f"Warning: {skill_target} exists and is not a symlink. Skipping.")
                    continue
            else:
                print(f"Skipping {skill_name}: target already exists.")
                continue
                
        # Create relative or absolute symlink? The contract says:
        # source repository -> validated state -> symlink -> runtime
        # We use absolute symlink for simplicity across directories
        os.symlink(os.path.abspath(skill_source), skill_target)
        print(f"Installed (symlink): {skill_name} -> {skill_target}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install skills via symlinks per docs/rules/skill_installation_and_deployment.md")
    parser.add_argument("--source", default="skills/universal", help="Source directory containing skills")
    parser.add_argument("--target", default=os.path.expanduser("~/.gemini/config/skills"), help="Target runtime directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing symlinks")
    args = parser.parse_args()
    
    install_skills(args.source, args.target, args.force)
