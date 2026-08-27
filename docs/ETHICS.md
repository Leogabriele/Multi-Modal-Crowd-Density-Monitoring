# Ethics Guidance — Live Camera Deployment

This system, once pointed at a real live camera feed, is fundamentally
different from working with pre-existing research datasets: you are now
actively collecting data about real, identifiable people (and vehicles,
which can carry license plates — also personal data under GDPR) in real
time.

## What's currently low-risk (crowd_density module)

The density module outputs an **aggregate number and heatmap** — it does
not identify, track, or store information about specific individuals.
Aggregate crowd counting is generally considered lower-risk under GDPR than
identification/tracking, but "lower-risk" is not "risk-free":

- Don't record/store raw video from a real public space without a clear
  legal basis (e.g. legitimate public-safety interest, posted notice,
  institutional approval) — even if your *output* is just an aggregate
  count, the *input* video may still contain identifiable people.
- Prefer running inference on live frames without persisting raw video to
  disk, if your only need is the aggregate count. If you do need to save
  footage (e.g. for later re-training), treat it as personal data:
  restrict access, don't publish it, and delete it when no longer needed.
- If you deploy this anywhere beyond your own private testing (e.g. a
  university corridor, a lab demo with volunteers), get explicit sign-off
  from whoever manages that space, and post a visible notice that cameras
  are recording for a research project.

## What's higher-risk (planned modules)

- **Vehicle classification / wrong-way detection**: if your pipeline ever
  captures or could reconstruct license plates, that's personal data under
  GDPR, full stop — this needs a proper legal basis, not just "it's a
  public road."
- **Suspicious behavior detection**: flagging specific individuals as
  "suspicious" is exactly the kind of output that needs the most caution.
  Keep outputs aggregate/pattern-level where possible (e.g. "unusual motion
  detected in zone 3") rather than tied to an identifiable person, and
  treat any deployment beyond your own private testing as needing formal
  ethics review before going further.

## For your PhD application specifically

None of this needs to be resolved before you apply — but demonstrating that
you've *thought about it* (which this document does) is itself a positive
signal to a Danish supervisor, since responsible AI is a genuine, actively
funded national priority there (see the crowd-anomaly project's literature
notes). If your application materials describe this system, include a
short line acknowledging these constraints rather than presenting it as
deployment-ready surveillance — that's both more honest and reads as more
mature to a reviewer.

## Practical rule of thumb while you're developing/testing

Test on: yourself, consenting friends/family, in a private space (your
room, a lab). Don't test on: a real public street, market, or any space
with non-consenting strangers, until you have institutional ethics
approval to do so.
