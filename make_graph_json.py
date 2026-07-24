import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

JST = timezone(
    timedelta(hours=9)
)

def get_history(ofc_cd, obs_cd):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # 最大30分前まで探す
    for offset in range(0, 30, 10):

        target = (
            datetime.now(JST)
            - timedelta(minutes=20 + offset)
        )

        minute = (
            target.minute // 10
        ) * 10

        date_part = target.strftime(
            "%Y%m%d"
        )

        time_part = (
            f"{target.hour:02d}"
            f"{minute:02d}"
        )

        file_ids = [

            f"0{ofc_cd}004{int(obs_cd):05d}",

            f"{ofc_cd}004{int(obs_cd):05d}"

        ]

        for file_id in file_ids:

            url = (
                f"https://www.river.go.jp/kawabou/file/files/tmlist/stg/"
                f"{date_part}/{time_part}/{file_id}.json"
            )

            try:

                r = requests.get(
                    url,
                    headers=headers,
                    timeout=5
                )

                if r.status_code != 200:
                    continue

                data = r.json()

                if "min10Values" not in data:
                    continue

                print(
                    f"{ofc_cd}-{obs_cd}",
                    f"{date_part} {time_part}",
                    file_id,
                    "取得成功"
                )

                return data["min10Values"]

            except Exception:

                continue

    return None

def create_graph_json(row):

    try:

        history = get_history(
            str(row["ofc_code"]),
            str(row["obs_code"])
        )

        if history is None:
            print(
                row["station_name"],
                "history=None"
            )
            return

        records = []

        for item in history:

            records.append({

                "obsTime": item["obsTime"],

                "stg":
                    item["stg"]
                    if (
                        item.get("stgCcd") == 0
                        and
                        item.get("stg") is not None
                    )
                    else None

            })

        if len(records) == 0:
            return

        graph_data = {
            "station_code": int(row["station_code"]),
            "river_system": row["river_system"],
            "station_name": row["station_name"],
            "station_kana": row["station_kana"],
            "river_name": row["river_name"],
            "river_kana": row["river_kana"],
            "water_url": row["water_url"],
            "camera_url": row["camera_url"],
            "standby_level": row["standby_level"],
            "warning_level": row["warning_level"],
            "evacuation_level": row["evacuation_level"],
            "danger_level": row["danger_level"],
            "history": records[::-1]
        }

        pd.Series(graph_data).to_json(
            f"graphs/{int(row['station_code'])}.json",
            force_ascii=False
        )

        print(
            row["station_name"],
            "完了"
        )

    except Exception as e:

        print(
            row["station_name"],
            "失敗",
            e
        )

# 観測所マスター
df = pd.read_excel(
    "stations.xlsx",
    sheet_name="suii",
    engine="openpyxl"
)

# graphsフォルダ
os.makedirs("graphs", exist_ok=True)

with ThreadPoolExecutor(
    max_workers=15
) as executor:

    executor.map(
        create_graph_json,
        [row for _, row in df.iterrows()]
    )

print("全観測所グラフJSON作成完了")
