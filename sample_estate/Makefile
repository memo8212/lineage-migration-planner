.PHONY: all extract mart publish

all: extract mart publish

extract:
	python3 python/transform.py

mart: extract
	sas -sysin sas/build_mart.sas

publish: mart
	cp /out/gold_segment.csv /archive/gold_segment.csv
