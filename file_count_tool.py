import argparse
import json
from pathlib import Path


STORE_PATH = Path(__file__).with_name("file_count_store.json")


def load_store() -> dict:
    if not STORE_PATH.exists():
        return {}

    with STORE_PATH.open("r", encoding="utf-8") as store_file:
        return json.load(store_file)


def save_store(store: dict) -> None:
    with STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, indent=2)


def count_files(directory: Path) -> int:
    return sum(1 for path in directory.rglob("*") if path.is_file())


def handle_count(directory_arg: str, name: str) -> None:
    directory = Path(directory_arg).expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    file_count = count_files(directory)
    store = load_store()
    store[name] = {
        "directory": str(directory),
        "file_count": file_count,
    }
    save_store(store)
    print(json.dumps(store[name], indent=2))


def handle_get(name: str) -> None:
    store = load_store()
    if name not in store:
        raise KeyError(f"No saved count found for name: {name}")

    print(json.dumps(store[name], indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Count files in a directory and save the result for later use."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    count_parser = subparsers.add_parser("count", help="Count files and save the result.")
    count_parser.add_argument("directory", help="Directory to count files in.")
    count_parser.add_argument(
        "--name",
        default="latest",
        help="Saved result name. Defaults to 'latest'.",
    )

    get_parser = subparsers.add_parser("get", help="Read a saved file count result.")
    get_parser.add_argument(
        "--name",
        default="latest",
        help="Saved result name. Defaults to 'latest'.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "count":
        handle_count(args.directory, args.name)
        return

    if args.command == "get":
        handle_get(args.name)
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
