import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from seed import main  # noqa
if __name__ == "__main__":
    main()
