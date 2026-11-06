import difflib
import json

diff1 = 'abc\ncdd\n'
diff2 = 'abc\nccd\n'

def diff_file( a : str,b :str ) -> str:
    res = difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="before.txt",
        tofile="after.txt",
        lineterm="\n",
    )

    part = [];
    
    for line in res:
        part.append(line)

        if not line.endswith("\n"):
            part.append("\n\\ No newline at end of file\n")

    return ''.join(part)

if __name__ == "__main__":
    result = diff_file(diff1,diff2)
    print(result, end="")
    