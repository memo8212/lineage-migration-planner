"""transform.py — build the gold segment mart from the clean cards feed."""
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.appName("gold_segment").getOrCreate()

cards = spark.read.table("CARDS_CLEAN")
cust = spark.read.table("CUSTOMER_DIM")

gold = (cards.join(cust, "ACCOUNT_NO")
             .groupBy("ACCOUNT_NO", "SEGMENT")
             .agg(F.sum("AMOUNT").alias("TOTAL")))

gold.write.mode("overwrite").saveAsTable("GOLD_SEGMENT")
gold.write.mode("overwrite").parquet("/out/gold_segment.parquet")

spark.sql("""
    CREATE OR REPLACE TABLE GOLD_SEGMENT_DAILY AS
    SELECT SEGMENT, SUM(TOTAL) AS SEGMENT_TOTAL
    FROM   GOLD_SEGMENT
    GROUP  BY SEGMENT
""")
