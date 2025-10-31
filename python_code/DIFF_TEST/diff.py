import difflib

def show_file_differences(file1_path, file2_path):
    """Prints the unified diff of two text files."""
    try:
        with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()

        diff = difflib.unified_diff(lines1, lines2, fromfile=file1_path, tofile=file2_path, lineterm='')
        for line in diff:
            print(line)
    except FileNotFoundError:
        print("One or both files not found.")

# Example usage
file_old = "path/to/old_version.txt"
file_new = "path/to/new_version.txt"

print(f"Differences between {file_old} and {file_new}:")
show_file_differences(file_old, file_new)