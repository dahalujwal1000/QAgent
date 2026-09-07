"""Deliberately vulnerable sample for tests/fixtures — DO NOT USE in production."""

import sqlite3
import hashlib
import subprocess


def get_user(name):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    # SQL injection
    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
    return cur.fetchone()


def hash_password(pw):
    # Insecure: md5 for passwords
    return hashlib.md5(pw.encode()).hexdigest()


def run(cmd):
    # Command injection risk
    return subprocess.run(cmd, shell=True)