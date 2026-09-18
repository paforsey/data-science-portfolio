# Rate Plan Cannibalization

Would a lower-priced wireless plan, `essentials`, add margin or mostly pull customers down from
higher-margin plans? This case study forecasts how many households would take it, where each would
otherwise have been, and the 12-month contribution margin of 108 launch configurations
(9 prices × 4 feature bundles × 3 eligibility rules), then scores every forecast against a withheld
answer key.

All data is synthetic. Plan names, prices, and features are illustrative.

## Notebooks

| Notebook | Sections | What it does | Run time |
|---|---|---|---|
| `data/00_generate_and_validate_data.ipynb` | — | Generates the market, plan history, conjoint survey, and withheld counterfactual launch; validates them | ~35 s |
| `01_choice_model_estimation.ipynb` | 01–04 | Revealed-preference baseline, stated-preference mixed logit, joint RP–SP nested model, latent taste classes | ~10 min |
| `02_launch_forecast.ipynb` | 05–08 | Back-test on the earlier `value` launch, launch simulation, scoring against the answer key, recommendation and rollout design | ~5 min |

Run them in that order. Notebook 01 writes handoff tables to `outputs/`, which notebook 02 reads.
`outputs/` is not tracked; rerun the notebooks to regenerate it.

The modeling notebooks load data through `load()`, which refuses the answer-key tables. Those load
only through `load_answer_key()`, and only in cells that score a finished forecast.

## Web page

Both notebooks build into one research-notebook page with a tab per section. Execute both, then from
this folder:

```bash
python3 ../../tools/notebook-restyle/merge_notebooks.py rate_plan_cannibalization.merged.ipynb \
    01_choice_model_estimation.ipynb 02_launch_forecast.ipynb
jupyter nbconvert --to html rate_plan_cannibalization.merged.ipynb --output rate_plan_cannibalization.export
python3 ../../tools/notebook-restyle/restyle_notebook.py web/notebook_config.py \
    rate_plan_cannibalization.export.html web/rate_plan_cannibalization.html
rm rate_plan_cannibalization.export.html
```

The merged notebook and the built page are build artifacts and are not tracked; the nbconvert export is only an intermediate step and is deleted after the page is built. Headline
figures and key decisions on the page live in `web/notebook_config.py`.
