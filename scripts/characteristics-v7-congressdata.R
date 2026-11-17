# Optional acquisition reader; normalized-evidence/model replay does not require R.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3)
suppressPackageStartupMessages(library(fst))
columns <- c(
  "state", "st", "firstname", "lastname", "bioguide", "year", "start", "end",
  "district_number", "congress_number", "icpsr", "party", "gender", "birthday",
  "inc_race", "inc_educ_undergrad", "inc_educ_postgrad", "inc_pol_exp_any",
  "inc_pol_exp_stleg", "inc_pol_exp_stwd", "inc_pol_exp_local",
  "inc_business_exp", "inc_law_exp", "inc_trades_exp", "inc_educ_exp",
  "inc_farming_exp", "MILITARY", "COL_MIL", "PRIOR_5", "PRIOR_3",
  "military_rank", "education", "military"
)
metadata <- metadata_fst(args[1])
selected <- intersect(columns, metadata$columnNames)
data <- read_fst(args[1], columns = selected)
write.csv(data, file.path(args[3], "congressdata-selected-member-years.csv"),
          row.names = FALSE, na = "")
write.csv(read_fst(args[2]),
          file.path(args[3], "congressdata-current-codebook.csv"),
          row.names = FALSE, na = "")
writeLines(c(R.version.string, paste("fst", packageVersion("fst")),
             paste("rows", metadata$nrOfRows),
             paste("columns", length(metadata$columnNames))),
           file.path(args[3], "congressdata-reader.txt"))
