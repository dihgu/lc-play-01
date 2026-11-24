#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laf Cambazı — metin tabanlı, Boggle benzeri kelime oyunu.

Özellikler
- 4x4 veya 8x8 tahta
- Türkçe karakter desteği (Ç, Ğ, İ, Ö, Ş, Ü)
- Komşuluk (8-yön) kuralına göre kelime doğrulama
- Sözlük doğrulaması (gömülü mini liste + opsiyonel sozluk.txt)
- Puanlama: 3→1, 4→2, 5→3, 6+ → (harf sayısı - 3)
- Tahtayı saat yönünde 90° döndürme
- Aynı kelimeyi tekrar saymama

Kullanım
$ python laf_cambazi.py

İpucu: Aynı klasöre bir "sozluk.txt" (UTF-8) koyarsan satır başına bir kelime olacak şekilde
sözlüğün kapsamını genişletebilirsin.
"""
from __future__ import annotations
import os
import random
import sys
from typing import List, Set, Tuple

# --- Türkçe büyük/küçük dönüştürme yardımcıları ---
_TR_UP = str.maketrans({
    'i': 'İ', 'ı': 'I', 'ş': 'Ş', 'ğ': 'Ğ', 'ü': 'Ü', 'ö': 'Ö', 'ç': 'Ç'
})
_TR_LOW = str.maketrans({
    'İ': 'i', 'I': 'ı', 'Ş': 'ş', 'Ğ': 'ğ', 'Ü': 'ü', 'Ö': 'ö', 'Ç': 'ç'
})

def tr_upper(s: str) -> str:
    return s.translate(_TR_UP).upper()

def tr_lower(s: str) -> str:
    return s.translate(_TR_LOW).lower()

# --- Harf dağılımı (yaklaşık Türkçe frekans, oyun dengesi için) ---
# Not: Boggle küpleri yerine basit bir ağırlıklı seçim kullanıyoruz.
LETTER_WEIGHTS = {
    'A': 12, 'E': 9, 'İ': 8, 'I': 6, 'N': 6, 'R': 6, 'L': 6, 'K': 5, 'M': 5, 'T': 5,
    'U': 5, 'Y': 5, 'O': 4, 'S': 4, 'B': 3, 'D': 3, 'H': 3, 'P': 3,
    'Ç': 2, 'Ö': 2, 'Ü': 2, 'G': 2, 'Z': 2,
    'Ş': 1, 'V': 1, 'C': 1, 'F': 1, 'J': 1, 'Ğ': 1, 'Q': 0, 'W': 0, 'X': 0
}
LETTERS, WEIGHTS = zip(*[(k, v) for k, v in LETTER_WEIGHTS.items() if v > 0])

# --- Gömülü mini sözlük (örnek). sozluk.txt ile genişletilir. ---
EMBEDDED_WORDS = {
    # kısa örnekler — oyunu test etmek için yeterli
    'KİTAP', 'KALE', 'KİT', 'KATİP', 'KATAR', 'MORAL', 'ORAL', 'PARE', 'PİTA', 'PİT',
    'MEN', 'MERA', 'PERA', 'SAREN', 'SEREN', 'İTAL', 'KİP', 'MOR', 'KİRAL', 'LİMAN',
    'LAF', 'CAMBAZ', 'KELİME', 'OYUN', 'TAHTA', 'HARF', 'SÜRE', 'PUAN'
}

# Sözlük yükleme

def load_dictionary(path: str = 'sozluk.txt') -> Set[str]:
    words: Set[str] = set(EMBEDDED_WORDS)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    w = tr_upper(line.strip())
                    if len(w) >= 3 and w.isalpha():
                        words.add(w)
        except Exception as e:
            print(f"Sözlük yüklenirken hata: {e}")
    return words

# Tahta oluşturma ve yardımcılar

def make_board(size: int, seed: int | None = None) -> List[List[str]]:
    rng = random.Random(seed)
    choices = [c for c, w in zip(LETTERS, WEIGHTS) for _ in range(w)]
    return [[rng.choice(choices) for _ in range(size)] for _ in range(size)]


def rotate_board(board: List[List[str]]) -> List[List[str]]:
    # Saat yönünde 90° döndür
    n = len(board)
    return [[board[n-1-j][i] for j in range(n)] for i in range(n)]


def print_board(board: List[List[str]]):
    n = len(board)
    print('\n' + ' '.join(['─'*3]*n))
    for row in board:
        print('  '.join(f"{c:2s}" for c in row))
    print(' ')

# Komşuluk kontrollü kelime bulunabilirlik araması (DFS)

def can_form_word(board: List[List[str]], word: str) -> bool:
    n = len(board)
    word = tr_upper(word)
    if len(word) < 3:
        return False

    # Hızlı filtre: harf çokluluğu kontrolü
    from collections import Counter
    board_counts = Counter(c for row in board for c in row)
    word_counts = Counter(word)
    for ch, cnt in word_counts.items():
        if board_counts.get(ch, 0) < cnt:
            return False

    # 8 yön: (dx, dy)
    dirs = [
        (-1,-1), (-1,0), (-1,1),
        (0,-1),          (0,1),
        (1,-1),  (1,0),  (1,1)
    ]

    def dfs(i: int, x: int, y: int, used: Set[Tuple[int,int]]) -> bool:
        if board[x][y] != word[i]:
            return False
        if i == len(word) - 1:
            return True
        used.add((x,y))
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in used:
                if dfs(i+1, nx, ny, used):
                    used.remove((x,y))  # backtrack step paired at return
                    return True
        used.remove((x,y))
        return False

    for x in range(n):
        for y in range(n):
            if board[x][y] == word[0]:
                if dfs(0, x, y, set()):
                    return True
    return False

# Puanlama

def score_word(w: str) -> int:
    L = len(w)
    if L < 3:
        return 0
    if L == 3:
        return 1
    if L == 4:
        return 2
    if L == 5:
        return 3
    return L - 3

# Oyun döngüsü

def game_loop():
    print("Laf Cambazı — metin tabanlı\n")
    while True:
        size_in = input("Tahta boyutu (4 veya 8, q=çık): ").strip()
        if size_in.lower() == 'q':
            print("Görüşürüz")
            return
        if size_in not in {'4','8'}:
            print("Lütfen 4 veya 8 gir.")
            continue
        size = int(size_in)
        break

    seed = None
    seed_in = input("İsteğe bağlı tohum (rastgeleliği sabitlemek için sayı, boş bırak=rasgele): ").strip()
    if seed_in:
        try:
            seed = int(seed_in)
        except ValueError:
            print("Geçersiz tohum, rasgele üretilecek.")
            seed = None

    words_dict = load_dictionary()
    board = make_board(size, seed=seed)
    found: Set[str] = set()
    total_score = 0

    print_board(board)
    print("Komutlar: kelime yaz • 'd' = döndür • 'l' = liste • 'y' = yeniden tahta • 's' = skor • 'q' = çık\n")

    while True:
        cmd = input("> ").strip()
        if not cmd:
            continue
        if cmd.lower() == 'q':
            break
        if cmd.lower() == 's':
            print(f"Toplam skor: {total_score} — Bulunan {len(found)} kelime")
            continue
        if cmd.lower() == 'l':
            if found:
                print("Buldukların:", ', '.join(sorted(found)))
            else:
                print("Henüz kelime yok.")
            continue
        if cmd.lower() == 'd':
            board = rotate_board(board)
            print_board(board)
            continue
        if cmd.lower() == 'y':
            board = make_board(size)
            found.clear()
            total_score = 0
            print_board(board)
            continue

        # Aksi halde girdi kelime varsayılır
        w = tr_upper(cmd)
        if len(w) < 3:
            print("En az 3 harf.")
            continue
        if w in found:
            print("Bu kelimeyi zaten buldun.")
            continue
        if w not in words_dict:
            print("Sözlükte yok.")
            continue
        if not can_form_word(board, w):
            print("Tahtada komşuluk kuralına uymuyor.")
            continue

        pts = score_word(w)
        found.add(w)
        total_score += pts
        print(f"+{pts} puan — Toplam: {total_score}")

    print(f"\nOyun bitti. Toplam skor: {total_score}")


if __name__ == '__main__':
    try:
        game_loop()
    except KeyboardInterrupt:
        print("\nÇıkıldı.")
