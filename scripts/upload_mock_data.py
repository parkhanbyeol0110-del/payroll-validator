"""
sample_data/mock_companies 의 파일들을 실제 업로드 API로 순서대로(1월 -> 2월) 전송한다.
로컬/운영 어디든 --url 로 대상 서버를 지정해 사용할 수 있다.

사용 예:
    python scripts/upload_mock_data.py --url http://127.0.0.1:5000
    python scripts/upload_mock_data.py --url https://payroll-validator-rho.vercel.app
"""
import argparse
import glob
import os
import re

import requests

COMPANIES = ["세종물류", "한빛전자", "그린테이블푸드", "파인트리소프트"]
MOCK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data", "mock_companies")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin1234")
    args = parser.parse_args()

    s = requests.Session()
    r = s.post(f"{args.url}/login", data={"username": args.username, "password": args.password})
    r.raise_for_status()
    print("login:", r.status_code, r.url)

    for company in COMPANIES:
        for month in ["2026-01", "2026-02"]:
            path = os.path.join(MOCK_DIR, f"{company}_{month}.xlsx")
            if not os.path.exists(path):
                print("skip (not found):", path)
                continue
            with open(path, "rb") as f:
                r = s.post(
                    f"{args.url}/upload",
                    data={"client_name": company, "payroll_month": month},
                    files={"payroll_file": (os.path.basename(path), f,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            print(f"{company} {month}: {r.status_code} {r.url}")


if __name__ == "__main__":
    main()
