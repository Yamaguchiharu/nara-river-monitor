import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

JST = timezone(
    timedelta(hours=9)
)

def get_water_level(ofc_cd, obs_cd):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for offset in range(0, 30, 10):

        target = (
            datetime.now(JST)
            - timedelta(minutes=5 + offset)
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

                if (
                    data.get("obsValue") is not None
                    and
                    data["obsValue"].get("stg") is not None
                ):

                        MISSING_CODES = [
                            140,
                            160,
                            190
                        ]

                        if (
                            data["obsValue"].get("stgCcd")
                            in MISSING_CODES
                        ):

                            return {
                                "water_level": None,
                                "obs_time": data["obsValue"]["obsTime"],
                                "change_10m": None
                            }

                        return {
                            "water_level": data["obsValue"]["stg"],
                            "obs_time": data["obsValue"]["obsTime"],
                            "change_10m": data["obsValue"]["stg10mChg"]
                        }

                for item in data.get("min10Values", []):

                    if item.get("stgCcd") == 0:

                        return {
                            "water_level": item["stg"],
                            "obs_time": item["obsTime"],
                            "change_10m": item["stg10mChg"]
                        }

                latest = data.get(
                    "min10Values",
                    []
                )

                if len(latest) > 0:

                    return {
                        "water_level": None,
                        "obs_time": latest[0]["obsTime"],
                        "change_10m": None
                    }

                return None

            except Exception:
                continue

    return None

def get_status_level(
    water_level,
    standby_level,
    warning_level,
    evacuation_level,
    danger_level
):

    if water_level is None:
        return 9

    if water_level >= danger_level:
        return 4

    if water_level >= evacuation_level:
        return 3

    if water_level >= warning_level:
        return 2

    if water_level >= standby_level:
        return 1

    return 0

def create_station_record(row):

    try:

        result = get_water_level(
            str(row["ofc_code"]),
            str(row["obs_code"])
        )

        if result is None:
            return None

        status_level = get_status_level(
            result["water_level"],
            row["standby_level"],
            row["warning_level"],
            row["evacuation_level"],
            row["danger_level"]
        )

        if row["station_name"] == "瓦口":
            print(
                result["water_level"],
                row["standby_level"],
                row["warning_level"],
                row["evacuation_level"],
                row["danger_level"],
                status_level
            )

        return {
           "station_code": row["station_code"],
           "station_name": row["station_name"],
           "region": row["region"],
           "river_system": row["river_system"],
           "river_name": row["river_name"],
           "latitude": row["latitude"],
           "longitude": row["longitude"],
           "water_level": result["water_level"],
           "obs_time": result["obs_time"],
           "change_10m": result["change_10m"],
           "status_level": status_level,
           "camera_url":
               None
               if pd.isna(row["camera_url"])
               else row["camera_url"],
           "water_url":
               None
               if pd.isna(row["water_url"])
               else row["water_url"],
        }

    except Exception as e:

        print(
            row["station_name"],
            "取得失敗",
            e
        )

        return None

df = pd.read_excel(
    "stations.xlsx",
    sheet_name="suii",
    engine="openpyxl"
)

print(df.dtypes)

level_cols = [
    "standby_level",
    "warning_level",
    "evacuation_level",
    "danger_level"
]

for col in level_cols:

    df[col] = (
        df[col]
        .astype(str)
        .str.replace("\u00A0", "", regex=False)
        .str.strip()
    )

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

with ThreadPoolExecutor(
    max_workers=15
) as executor:

    results = list(
        executor.map(
            create_station_record,
            (row for _, row in df.iterrows())
        )
    )

records = [
    r for r in results
    if r is not None
]

result = {
    "updated_at": datetime.now(JST).strftime(
        "%Y/%m/%d %H:%M"
    ),
    "stations": records
}

import json

with open(
    "latest_water_level.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        result,
        f,
        ensure_ascii=False,
        allow_nan=False
    )

print(df.columns.tolist())
print("件数:", len(records))
print("保存完了")