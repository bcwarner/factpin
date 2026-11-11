# factpin

Refer to constants your script or notebook computes the way you would with `\cite` or
`\ref`.

```bash
pip install factpin
```

## Example

```python
import factpin

ctx = factpin.Context("results")                       # -> ./results.tex
ctx.add_group("auroc", places=3, format="ci")
ctx.add_group("latency", unit=r"\milli\second", places=1)

ctx.add("auroc_a_ci", values=[0.5017, 0.4523, 0.5488], group="auroc")
ctx.add("train_time", value=12.3456, group="latency")
ctx.add("n_patients", value=1234)
ctx.add_text("best_model", "Logistic regression")

ctx.write()
```

```latex
\usepackage{factpin}
\input{results}

Across \const{n_patients} patients the AUROC was \const{auroc_a_ci}, and training
took \const{train_time}.
% -> Across 1234 patients the AUROC was 0.502 (95% CI: 0.452 to 0.549), and
%    training took 12.3 ms.
```

`factpin.sty` is the corresponding style definition file for `\const`. `python -m factpin install-sty` prints
it, ready to paste into a new `factpin.sty` file on Overleaf. Can also be copied to a directory with 
(`python -m factpin install-sty path/to/project`).

## License

MIT
