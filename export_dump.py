import pymysql
import os

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='passwd',
    database='sddra_billing',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

out_file = os.path.join(os.path.dirname(__file__), 'sddra_billing_dump.sql')

with open(out_file, 'w', encoding='utf-8') as f:
    f.write("-- ==========================================================\n")
    f.write("-- SDDRA Billing System - Complete Cloud MySQL Database Dump\n")
    f.write("-- Database: sddra_billing\n")
    f.write("-- ==========================================================\n\n")
    f.write("CREATE DATABASE IF NOT EXISTS `sddra_billing` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n")
    f.write("USE `sddra_billing`;\n\n")
    f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

    with conn.cursor() as cur:
        cur.execute("SHOW TABLES;")
        tables = [list(r.values())[0] for r in cur.fetchall()]

        for t in tables:
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"-- Table structure for `{t}`\n")
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"DROP TABLE IF EXISTS `{t}`;\n")
            
            cur.execute(f"SHOW CREATE TABLE `{t}`;")
            create_stmt = cur.fetchone()['Create Table']
            f.write(f"{create_stmt};\n\n")

            # Fetch rows
            cur.execute(f"SELECT * FROM `{t}`;")
            rows = cur.fetchall()
            if rows:
                f.write(f"-- Dumping data for `{t}` ({len(rows)} rows)\n")
                for r in rows:
                    cols = ", ".join([f"`{k}`" for k in r.keys()])
                    vals = []
                    for v in r.values():
                        if v is None:
                            vals.append("NULL")
                        elif isinstance(v, (int, float)):
                            vals.append(str(v))
                        else:
                            # Escape single quotes and backslashes
                            escaped = str(v).replace("\\", "\\\\").replace("'", "\\'")
                            vals.append(f"'{escaped}'")
                    vals_str = ", ".join(vals)
                    f.write(f"INSERT INTO `{t}` ({cols}) VALUES ({vals_str});\n")
                f.write("\n")

    f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

conn.close()
print(f"Exported complete database dump to: {out_file}")
