import math
import time
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import ttk

from laf_cambazi import can_form_word, load_dictionary, make_board, rotate_board, tr_upper


ROUND_SECONDS_BY_SIZE = {4: 120, 6: 150, 8: 150}


def format_timer(seconds):
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"
CIRCUMFLEX_LETTERS = str.maketrans("ÂÎÛ", "AIU")


def normalize_word(word):
    return tr_upper(unicodedata.normalize("NFC", word.strip())).translate(CIRCUMFLEX_LETTERS)


def load_game_words(folder):
    words = {normalize_word(word) for word in load_dictionary(folder / "sozluk.txt")}
    edits = folder / "sozluk_duzeltmeleri.txt"
    if edits.is_file():
        for line in edits.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line[0] not in "+-":
                continue
            word = normalize_word(line[1:])
            if not word.isalpha() or len(word) < 3:
                continue
            if line[0] == "+":
                words.add(word)
            else:
                words.discard(word)
    return words


def find_board_words(board, dictionary, minimum_length):
    size = len(board)
    letters = {letter for row in board for letter in row}
    candidates = {
        word for word in dictionary
        if minimum_length <= len(word) <= size * size and set(word) <= letters
    }
    prefixes = {word[:length] for word in candidates for length in range(1, len(word))}
    neighbors = {
        (row, col): [
            (r, c)
            for r in range(max(0, row - 1), min(size, row + 2))
            for c in range(max(0, col - 1), min(size, col + 2))
            if (r, c) != (row, col)
        ]
        for row in range(size) for col in range(size)
    }
    found = set()
    visited = set()

    def search(position, prefix):
        row, col = position
        word = prefix + board[row][col]
        if word in candidates:
            found.add(word)
        if word in prefixes:
            visited.add(position)
            for neighbor in neighbors[position]:
                if neighbor not in visited:
                    search(neighbor, word)
            visited.remove(position)

    for position in neighbors:
        search(position, "")
    return found


class LafCambazi:
    def __init__(self, root):
        self.words = load_game_words(Path(__file__).parent)
        self.deadline = None
        self.paused_remaining = None
        self.board = []
        self.path = []
        self.found = set()
        self.score = 0
        self.tiles = {}

        root.title("Laf Cambazı")
        root.resizable(False, False)
        shell = ttk.Frame(root, padding=20)
        shell.pack()
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Laf Cambazı", font=("Helvetica", 24, "bold")).pack(anchor="w")
        controls = ttk.Frame(header)
        controls.pack(fill="x", pady=(8, 0))
        self.size = tk.IntVar(value=4)
        self.start_button = ttk.Button(controls, text="Başla", command=self.start_round)
        self.start_button.pack(side="left")
        self.pause_button = ttk.Button(
            controls, text="Developer Tool · Kapalı", command=self.toggle_pause,
        )
        self.pause_button.pack(side="left", padx=8)
        self.timer_text = ttk.Label(controls, font=("Helvetica", 20, "bold"))
        self.timer_text.pack(side="right")
        self.size.trace_add("write", self.show_selected_duration)
        self.show_selected_duration()
        self.previews = ttk.Frame(header)
        self.previews.pack(fill="x", pady=(10, 0))
        self.size_buttons = []
        for size in (4, 6, 8):
            self.add_size_preview(size)
        self.timeout_banner = tk.Label(
            header, text="Süre doldu!", background="#ad241c", foreground="#ffffff",
            font=("Helvetica", 18, "bold"), pady=8,
        )

        body = ttk.Frame(shell)
        body.pack(fill="both")
        panel = ttk.Frame(body)
        panel.pack(side="left", fill="both")
        self.grid = ttk.Frame(panel)
        self.grid.pack()

        sidebar = ttk.Frame(body, padding=(16, 0, 0, 0))
        sidebar.pack(side="right", fill="y")
        self.score_text = ttk.Label(sidebar, text="Puan 0", font=("Helvetica", 18, "bold"))
        self.score_text.pack(anchor="w", pady=(0, 8))
        ttk.Label(sidebar, text="Gönderilen kelimeler").pack(anchor="w", pady=(0, 4))
        word_list = ttk.Frame(sidebar)
        word_list.pack(fill="both", expand=True)
        self.word_list = tk.Listbox(word_list, width=32, height=7, takefocus=False)
        scrollbar = ttk.Scrollbar(word_list, orient="vertical", command=self.word_list.yview)
        self.word_list.configure(yscrollcommand=scrollbar.set)
        self.word_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.word_text = tk.StringVar()
        self.entry = ttk.Entry(panel, textvariable=self.word_text, justify="center",
                               font=("Helvetica", 19, "bold"), width=17)
        self.entry.pack(pady=(12, 4))
        self.word_text.trace_add("write", self.on_word_edited)
        self.status = ttk.Label(panel, wraplength=320, justify="center")
        self.status.pack(pady=(0, 10))

        actions = ttk.Frame(panel)
        actions.pack()
        self.play_buttons = []
        for label, command in (
            ("Çevir (⌘R)", self.rotate), ("Gönder", self.submit)
        ):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side="left", padx=4)
            self.play_buttons.append(button)
        root.bind("<Return>", lambda event: self.submit())
        root.bind("<Escape>", lambda event: self.clear())
        root.bind("<Command-r>", self.rotate_shortcut)
        self.set_playing(False)
        self.status.configure(text="Tahta boyutunu seçip Başla’ya bas.")
        self.root = root

    def add_size_preview(self, size):
        card = ttk.Frame(self.previews)
        card.pack(side="left", expand=True, fill="x", padx=4)
        button = ttk.Radiobutton(card, text=f"{size}×{size}", variable=self.size, value=size)
        button.pack()
        self.size_buttons.append(button)
        preview = tk.Canvas(card, width=96, height=96, background="#edf4f1",
                            highlightthickness=0, cursor="hand2")
        preview.pack(pady=(4, 0))
        cell = 96 / size
        for row, letters in enumerate(make_board(size, seed=size)):
            for col, letter in enumerate(letters):
                x, y = col * cell, row * cell
                preview.create_rectangle(x + 1, y + 1, x + cell - 1, y + cell - 1,
                                         fill="#d9e8e3", outline="")
                preview.create_text(x + cell / 2, y + cell / 2, text=letter,
                                    fill="#162c26", font=("Helvetica", min(12, int(cell) - 3)))
        preview.bind("<Button-1>", lambda event: button.invoke())

    def set_playing(self, playing):
        for widget in [self.entry, self.pause_button, *self.play_buttons]:
            widget.state(["!disabled" if playing else "disabled"])
        for widget in [self.start_button, *self.size_buttons]:
            widget.state(["disabled" if playing else "!disabled"])

    def show_selected_duration(self, *_):
        self.timer_text.configure(text=format_timer(ROUND_SECONDS_BY_SIZE[self.size.get()]))

    def start_round(self):
        if self.deadline is not None or self.paused_remaining is not None:
            return
        size = self.size.get()
        self.board = make_board(size)
        self.previews.pack_forget()
        self.timeout_banner.pack_forget()
        self.path.clear()
        self.found.clear()
        self.score = 0
        self.score_text.configure(text="Puan 0")
        self.word_list.delete(0, tk.END)
        for tile in self.tiles.values():
            tile.destroy()
        self.tiles.clear()
        tile_font, tile_padding = {4: (32, 14), 6: (27, 10), 8: (23, 7)}[size]
        for row, letters in enumerate(self.board):
            for col, letter in enumerate(letters):
                position = (row, col)
                tile = tk.Label(
                    self.grid, text=letter, width=3, height=1, padx=6, pady=tile_padding,
                    font=("Helvetica", tile_font, "bold"), cursor="hand2",
                    takefocus=True, highlightthickness=2,
                    highlightcolor="#17584c", highlightbackground="#d9e8e3",
                )
                tile.grid(row=row, column=col, padx=3, pady=3)
                tile.bind("<Button-1>", lambda event, pos=position: self.choose(pos))
                tile.bind("<space>", lambda event, pos=position: self.choose(pos))
                self.tiles[position] = tile

        self.set_playing(True)
        self.reset_input()
        self.show_instructions()
        self.deadline = time.monotonic() + ROUND_SECONDS_BY_SIZE[size]
        self.tick(self.deadline)

    def tick(self, deadline):
        if self.deadline == deadline and self.round_active():
            seconds = math.ceil(self.deadline - time.monotonic())
            self.timer_text.configure(text=format_timer(max(0, seconds)))
            self.root.after(100, self.tick, deadline)

    def toggle_pause(self):
        if not self.round_active():
            return
        if self.paused_remaining is None:
            self.paused_remaining = max(0, self.deadline - time.monotonic())
            self.deadline = None
            self.pause_button.configure(text="Developer Tool · Açık")
        else:
            self.deadline = time.monotonic() + self.paused_remaining
            self.paused_remaining = None
            self.pause_button.configure(text="Developer Tool · Kapalı")
            self.tick(self.deadline)
        self.entry.focus_set()

    def round_active(self):
        if self.paused_remaining is not None:
            return True
        if self.deadline is None:
            return False
        if time.monotonic() < self.deadline:
            return True
        self.deadline = None
        self.timer_text.configure(text="0:00")
        self.set_playing(False)
        self.previews.pack(fill="x", pady=(10, 0))
        self.timeout_banner.pack(fill="x", pady=(8, 0))
        self.status.configure(text="Yeni tur için Başla’ya bas.")
        missed = find_board_words(self.board, self.words, self.minimum_length()) - self.found
        heading_index = self.word_list.size()
        self.word_list.insert(tk.END, f"Bulamadıkların ({len(missed)})")
        self.word_list.itemconfigure(heading_index, background="#d9e8e3", foreground="#162c26")
        for word in sorted(missed):
            self.word_list.insert(tk.END, word)
        self.word_list.see(heading_index)
        return False

    def rotate_shortcut(self, event):
        self.rotate()
        return "break"

    def selected_word(self):
        return "".join(self.board[row][col] for row, col in self.path)

    def on_word_edited(self, *_):
        if self.path and self.word_text.get() != self.selected_word():
            self.path.clear()
            self.refresh()

    def refresh(self):
        selected = set(self.path)
        for position, tile in self.tiles.items():
            row, col = position
            tile.configure(text=self.board[row][col])
            if position in selected:
                tile.configure(background="#17584c", foreground="#ffffff")
            else:
                tile.configure(background="#d9e8e3", foreground="#162c26")

    def rotate(self):
        if not self.round_active():
            return
        last_index = len(self.board) - 1
        self.board = rotate_board(self.board)
        self.path = [(col, last_index - row) for row, col in self.path]
        self.status.configure(text="Tahta saat yönünde çevrildi.")
        self.entry.focus_set()
        self.refresh()

    def choose(self, position):
        if not self.round_active():
            return
        self.entry.focus_set()
        if self.path and position == self.path[-1]:
            self.path.pop()
        elif position in self.path:
            self.status.configure(text="Her kareyi bir kez kullanabilirsin.")
            return
        else:
            if self.path:
                row, col = position
                last_row, last_col = self.path[-1]
                if max(abs(row - last_row), abs(col - last_col)) > 1:
                    self.status.configure(text="Son harfe komşu bir kare seç.")
                    return
            self.path.append(position)
        self.status.configure(text="Çapraz kareler de komşu sayılır.")
        self.word_text.set(self.selected_word())
        self.entry.icursor(tk.END)
        self.refresh()

    def reset_input(self):
        self.path.clear()
        self.word_text.set("")
        self.refresh()
        self.entry.focus_set()

    def clear(self):
        if self.round_active():
            self.reset_input()
            self.show_instructions()

    def minimum_length(self):
        return 3 if len(self.board) == 4 else 4

    def show_instructions(self):
        self.status.configure(text=f"En az {self.minimum_length()} harfli bir kelime yazıp Enter’a bas.")

    def submit(self):
        if not self.round_active():
            return
        entered = self.word_text.get().strip()
        if not entered:
            return
        word = normalize_word(entered)
        if len(word) < self.minimum_length():
            message = f"Bu tahtada kelimeler en az {self.minimum_length()} harfli olmalı."
            result = "Çok kısa"
        elif word in self.found:
            message = f"{word} daha önce bulundu."
            result = "Tekrar"
        elif word not in self.words:
            message = f"{word} sözlükte yok."
            result = "Sözlükte yok"
        elif not self.path and not can_form_word(self.board, word):
            message = f"{word} tahtadaki komşu harflerle kurulamıyor."
            result = "Tahtada yok"
        else:
            points = len(word)
            self.found.add(word)
            self.score += points
            self.score_text.configure(text=f"Puan {self.score}")
            message = f"{word}  +{points} puan"
            result = f"+{points}"
        self.word_list.insert(tk.END, f"{entered}  ·  {result}")
        self.word_list.see(tk.END)
        self.reset_input()
        self.status.configure(text=message)


if __name__ == "__main__":
    window = tk.Tk()
    LafCambazi(window)
    window.mainloop()
