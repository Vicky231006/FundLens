-- 004: Calendar dimension, 2006-01-01 .. 2040-12-31.
-- is_observed_day / is_month_end are maintained after each load (marts refresh step).
INSERT INTO core.dim_date (date_key, cal_date, year, quarter, month, day_of_month,
                           iso_weekday, is_weekday)
SELECT to_char(d, 'YYYYMMDD')::int,
       d::date,
       extract(year FROM d)::smallint,
       extract(quarter FROM d)::smallint,
       extract(month FROM d)::smallint,
       extract(day FROM d)::smallint,
       extract(isodow FROM d)::smallint,
       extract(isodow FROM d) < 6
FROM generate_series('2006-01-01'::date, '2040-12-31'::date, interval '1 day') AS g(d);
