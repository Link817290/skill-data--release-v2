
I am responsible for the final review of group physical examination reports. The working directory contains complete examination details for 10 anonymized cases. Based on the provided materials, reconstruct doctor-reviewed final physical examination conclusions.
The case IDs range from VAL-001 to VAL-010.
Review all examination details for each case and generate standardized final conclusions. Do not report normal, negative, or insufficiently supported findings as abnormal conclusions. Retain each medical conclusion only once, while preserving medically meaningful information such as the organ, laterality, degree, echogenic characteristics, and accompanying features. For each conclusion, provide at least one supporting `明细行号`; separate multiple row numbers with semicolons. Where the review turns up nothing abnormal, leave that case out of the conclusion sheet entirely and mark it `无异常结论` in the case summary. 

Finally, generate:
1. `体检总检结论.xlsx`
   Retain the two worksheets `总检结论` and `病例汇总`.
   Fields in `总检结论`: `病例编号`, `结论序号`, `标准体检结论`, `证据明细行号`, and `判断说明`.
   `病例汇总` must contain exactly one row for each case, and `总检状态` must be either `有异常结论` or `无异常结论`.
