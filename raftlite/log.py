"""In-memory replicated log. Indices are 1-based, matching the Raft paper."""


class LogEntry:
    def __init__(self, term, command):
        self.term = term
        self.command = command

    def to_dict(self):
        return {"term": self.term, "command": self.command}

    @staticmethod
    def from_dict(d):
        return LogEntry(d["term"], d["command"])

    def __eq__(self, other):
        return isinstance(other, LogEntry) and self.term == other.term and self.command == other.command

    def __repr__(self):
        return f"LogEntry(term={self.term}, command={self.command!r})"


class RaftLog:
    def __init__(self):
        self.entries = []

    def last_index(self):
        return len(self.entries)

    def last_term(self):
        return self.entries[-1].term if self.entries else 0

    def term_at(self, index):
        if index <= 0 or index > len(self.entries):
            return 0
        return self.entries[index - 1].term

    def get(self, index):
        return self.entries[index - 1]

    def append(self, entry):
        self.entries.append(entry)

    def truncate_from(self, index):
        del self.entries[index - 1:]

    def slice_from(self, index):
        if index <= 0:
            return list(self.entries)
        return self.entries[index - 1:]
