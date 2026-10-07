-- reduction_annuelle is stored as an integer percentage rate (5 => 5%).
-- Backfill legacy fractional rows (0.05 => 5) before converting the column.

update public.abonnement
set reduction_annuelle = case
    when reduction_annuelle > 0 and reduction_annuelle < 1 then round(reduction_annuelle * 100)
    else round(reduction_annuelle)
end
where reduction_annuelle is not null;

alter table if exists public.abonnement
    alter column reduction_annuelle type integer using case
        when reduction_annuelle > 0 and reduction_annuelle < 1 then round(reduction_annuelle * 100)::integer
        else round(reduction_annuelle)::integer
    end,
    alter column reduction_annuelle set default 0;

