"""Metadata for all 66 books of the Bible."""

from dataclasses import dataclass


@dataclass
class BookInfo:
    name: str           # Full English name
    chapters: int       # Number of chapters
    abbreviation: str   # API abbreviation for labs.bible.org
    testament: str      # "OT" or "NT"
    directory: str      # Directory/filename slug
    group: str          # Book group for color coding
    long_title: str     # Geneva-style main title
    subtitle: str       # Geneva-style subtitle (may be empty)


BOOKS = [
    # Old Testament — Pentateuch
    BookInfo("Genesis", 50, "genesis", "OT", "genesis", "pentateuch",
             "The First Book of Moses", "Called Genesis"),
    BookInfo("Exodus", 40, "exodus", "OT", "exodus", "pentateuch",
             "The Second Book of Moses", "Called Exodus"),
    BookInfo("Leviticus", 27, "leviticus", "OT", "leviticus", "pentateuch",
             "The Third Book of Moses", "Called Leviticus"),
    BookInfo("Numbers", 36, "numbers", "OT", "numbers", "pentateuch",
             "The Fourth Book of Moses", "Called Numbers"),
    BookInfo("Deuteronomy", 34, "deuteronomy", "OT", "deuteronomy", "pentateuch",
             "The Fifth Book of Moses", "Called Deuteronomy"),
    # Old Testament — Historical
    BookInfo("Joshua", 24, "joshua", "OT", "joshua", "historical",
             "The Book of Joshua", ""),
    BookInfo("Judges", 21, "judges", "OT", "judges", "historical",
             "The Book of Judges", ""),
    BookInfo("Ruth", 4, "ruth", "OT", "ruth", "historical",
             "The Book of Ruth", ""),
    BookInfo("1 Samuel", 31, "1 samuel", "OT", "1samuel", "historical",
             "The First Book of Samuel", "Otherwise Called the First Book of the Kings"),
    BookInfo("2 Samuel", 24, "2 samuel", "OT", "2samuel", "historical",
             "The Second Book of Samuel", "Otherwise Called the Second Book of the Kings"),
    BookInfo("1 Kings", 22, "1 kings", "OT", "1kings", "historical",
             "The First Book of the Kings", "Commonly Called the Third Book of the Kings"),
    BookInfo("2 Kings", 25, "2 kings", "OT", "2kings", "historical",
             "The Second Book of the Kings", "Commonly Called the Fourth Book of the Kings"),
    BookInfo("1 Chronicles", 29, "1 chronicles", "OT", "1chronicles", "historical",
             "The First Book of the Chronicles", ""),
    BookInfo("2 Chronicles", 36, "2 chronicles", "OT", "2chronicles", "historical",
             "The Second Book of the Chronicles", ""),
    BookInfo("Ezra", 10, "ezra", "OT", "ezra", "historical",
             "The Book of Ezra", ""),
    BookInfo("Nehemiah", 13, "nehemiah", "OT", "nehemiah", "historical",
             "The Book of Nehemiah", ""),
    BookInfo("Esther", 10, "esther", "OT", "esther", "historical",
             "The Book of Esther", ""),
    # Old Testament — Wisdom/Poetry
    BookInfo("Job", 42, "job", "OT", "job", "wisdom",
             "The Book of Job", ""),
    BookInfo("Psalms", 150, "psalms", "OT", "psalms", "wisdom",
             "The Book of Psalms", ""),
    BookInfo("Proverbs", 31, "proverbs", "OT", "proverbs", "wisdom",
             "The Proverbs", ""),
    BookInfo("Ecclesiastes", 12, "ecclesiastes", "OT", "ecclesiastes", "wisdom",
             "Ecclesiastes", "Or, the Preacher"),
    BookInfo("Song of Solomon", 8, "song of solomon", "OT", "songofsolomon", "wisdom",
             "The Song of Solomon", ""),
    # Old Testament — Major Prophets
    BookInfo("Isaiah", 66, "isaiah", "OT", "isaiah", "majorprophets",
             "The Book of the Prophet Isaiah", ""),
    BookInfo("Jeremiah", 52, "jeremiah", "OT", "jeremiah", "majorprophets",
             "The Book of the Prophet Jeremiah", ""),
    BookInfo("Lamentations", 5, "lamentations", "OT", "lamentations", "majorprophets",
             "The Lamentations of Jeremiah", ""),
    BookInfo("Ezekiel", 48, "ezekiel", "OT", "ezekiel", "majorprophets",
             "The Book of the Prophet Ezekiel", ""),
    BookInfo("Daniel", 12, "daniel", "OT", "daniel", "majorprophets",
             "The Book of Daniel", ""),
    # Old Testament — Minor Prophets
    BookInfo("Hosea", 14, "hosea", "OT", "hosea", "minorprophets",
             "The Book of Hosea", ""),
    BookInfo("Joel", 3, "joel", "OT", "joel", "minorprophets",
             "The Book of Joel", ""),
    BookInfo("Amos", 9, "amos", "OT", "amos", "minorprophets",
             "The Book of Amos", ""),
    BookInfo("Obadiah", 1, "obadiah", "OT", "obadiah", "minorprophets",
             "The Book of Obadiah", ""),
    BookInfo("Jonah", 4, "jonah", "OT", "jonah", "minorprophets",
             "The Book of Jonah", ""),
    BookInfo("Micah", 7, "micah", "OT", "micah", "minorprophets",
             "The Book of Micah", ""),
    BookInfo("Nahum", 3, "nahum", "OT", "nahum", "minorprophets",
             "The Book of Nahum", ""),
    BookInfo("Habakkuk", 3, "habakkuk", "OT", "habakkuk", "minorprophets",
             "The Book of Habakkuk", ""),
    BookInfo("Zephaniah", 3, "zephaniah", "OT", "zephaniah", "minorprophets",
             "The Book of Zephaniah", ""),
    BookInfo("Haggai", 2, "haggai", "OT", "haggai", "minorprophets",
             "The Book of Haggai", ""),
    BookInfo("Zechariah", 14, "zechariah", "OT", "zechariah", "minorprophets",
             "The Book of Zechariah", ""),
    BookInfo("Malachi", 4, "malachi", "OT", "malachi", "minorprophets",
             "The Book of Malachi", ""),
    # New Testament — Gospels
    BookInfo("Matthew", 28, "matthew", "NT", "matthew", "gospels",
             "The Gospel According to Saint Matthew", ""),
    BookInfo("Mark", 16, "mark", "NT", "mark", "gospels",
             "The Gospel According to Saint Mark", ""),
    BookInfo("Luke", 24, "luke", "NT", "luke", "gospels",
             "The Gospel According to Saint Luke", ""),
    BookInfo("John", 21, "john", "NT", "john", "gospels",
             "The Gospel According to Saint John", ""),
    # New Testament — Acts
    BookInfo("Acts", 28, "acts", "NT", "acts", "acts",
             "The Acts of the Apostles", ""),
    # New Testament — Pauline Epistles
    BookInfo("Romans", 16, "romans", "NT", "romans", "pauline",
             "The Epistle of Paul the Apostle to the Romans", ""),
    BookInfo("1 Corinthians", 16, "1 corinthians", "NT", "1corinthians", "pauline",
             "The First Epistle of Paul the Apostle to the Corinthians", ""),
    BookInfo("2 Corinthians", 13, "2 corinthians", "NT", "2corinthians", "pauline",
             "The Second Epistle of Paul the Apostle to the Corinthians", ""),
    BookInfo("Galatians", 6, "galatians", "NT", "galatians", "pauline",
             "The Epistle of Paul the Apostle to the Galatians", ""),
    BookInfo("Ephesians", 6, "ephesians", "NT", "ephesians", "pauline",
             "The Epistle of Paul the Apostle to the Ephesians", ""),
    BookInfo("Philippians", 4, "philippians", "NT", "philippians", "pauline",
             "The Epistle of Paul the Apostle to the Philippians", ""),
    BookInfo("Colossians", 4, "colossians", "NT", "colossians", "pauline",
             "The Epistle of Paul the Apostle to the Colossians", ""),
    BookInfo("1 Thessalonians", 5, "1 thessalonians", "NT", "1thessalonians", "pauline",
             "The First Epistle of Paul the Apostle to the Thessalonians", ""),
    BookInfo("2 Thessalonians", 3, "2 thessalonians", "NT", "2thessalonians", "pauline",
             "The Second Epistle of Paul the Apostle to the Thessalonians", ""),
    BookInfo("1 Timothy", 6, "1 timothy", "NT", "1timothy", "pauline",
             "The First Epistle of Paul the Apostle to Timothy", ""),
    BookInfo("2 Timothy", 4, "2 timothy", "NT", "2timothy", "pauline",
             "The Second Epistle of Paul the Apostle to Timothy", ""),
    BookInfo("Titus", 3, "titus", "NT", "titus", "pauline",
             "The Epistle of Paul to Titus", ""),
    BookInfo("Philemon", 1, "philemon", "NT", "philemon", "pauline",
             "The Epistle of Paul to Philemon", ""),
    # New Testament — General Epistles
    BookInfo("Hebrews", 13, "hebrews", "NT", "hebrews", "general",
             "The Epistle to the Hebrews", ""),
    BookInfo("James", 5, "james", "NT", "james", "general",
             "The General Epistle of James", ""),
    BookInfo("1 Peter", 5, "1 peter", "NT", "1peter", "general",
             "The First Epistle General of Peter", ""),
    BookInfo("2 Peter", 3, "2 peter", "NT", "2peter", "general",
             "The Second Epistle General of Peter", ""),
    BookInfo("1 John", 5, "1 john", "NT", "1john", "general",
             "The First Epistle General of John", ""),
    BookInfo("2 John", 1, "2 john", "NT", "2john", "general",
             "The Second Epistle of John", ""),
    BookInfo("3 John", 1, "3 john", "NT", "3john", "general",
             "The Third Epistle of John", ""),
    BookInfo("Jude", 1, "jude", "NT", "jude", "general",
             "The General Epistle of Jude", ""),
    # New Testament — Revelation
    BookInfo("Revelation", 22, "revelation", "NT", "revelation", "revelation",
             "The Revelation of Saint John the Divine", ""),
]


def get_book_by_name(name: str) -> BookInfo | None:
    """Look up a book by name (case-insensitive, matches directory slug too)."""
    name_lower = name.lower().replace(" ", "")
    for book in BOOKS:
        if (book.name.lower().replace(" ", "") == name_lower
                or book.directory == name_lower):
            return book
    return None


def get_books_by_testament(testament: str) -> list[BookInfo]:
    """Get all books for a given testament ('OT' or 'NT')."""
    return [b for b in BOOKS if b.testament == testament]
