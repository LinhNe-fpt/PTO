import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from data_gen import gen_matrix_password

print('=== Seed: PTO2026 ===')
for n in range(1, 11):
    p = gen_matrix_password(n)
    print(f'  #{n:03d}: {p}  (len={len(p)})')

print()
print('=== Seed: MYSHOP2026 ===')
for n in range(1, 6):
    print(f'  #{n:03d}: {gen_matrix_password(n, seed="MYSHOP2026")}')

print()
print('=== Tai tao lai (cung n + seed -> cung password) ===')
for n in [1, 5, 10]:
    p1 = gen_matrix_password(n)
    p2 = gen_matrix_password(n)
    ok = 'OK' if p1 == p2 else 'FAIL'
    print(f'  #{n:03d}: {p1}  [{ok}]')
