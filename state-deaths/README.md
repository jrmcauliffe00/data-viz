# State deaths

Birth-to-death dispersal for notable people in Wikidata, one US birth state at a time. The notebook is `dispersal_analysis.ipynb`. Cached extracts and map HTML stay in the repo-root `data/` folder.

Open the notebook from this directory so `../data` resolves.

## Limitations

These maps describe a Wikidata extract of notable people who died on or after 1 January 1980. They do not describe the US resident population.

The extract is not one national sample. Each birth state is a separate query, capped at the 5,000 most recent deaths. Most states never reach that cap, so the files are different sizes. California has about 4,886 people. Alaska, Delaware, Vermont, and Wyoming each have about 150.

That size gap matters for the **US native deaths per state** map, which is a raw count of deaths located in each state. People tend to die in the state where they were born, so a state with a larger birth file contributes more deaths in that same state. California looks large on that map largely because its birth file is large.

The same-state death rate and the out-migration rate already divide by each birth state's own record count, so those comparisons are not driven by file size. They still describe Wikidata notables, not residents.

Two further limits on comparing states:

- States that hit the 5,000 cap are only their most recent deaths. States under the cap include their whole post-1980 notable set, so the time window is not the same.
- Rows with no resolvable US death state and no foreign country are left out of the rates. The death-location map draws those states as zero only when the extract has no resolved death there. Washington, D.C. is not in the 50-state extract.
