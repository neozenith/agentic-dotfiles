# Flowchart Node Reference

Standard flowchart shapes from `diagrams.programming.flowchart`.

## Import

```python
from diagrams.programming.flowchart import (
    Action,              # Rectangle — process/action step
    Collate,             # Hourglass — collation operation
    Database,            # Cylinder — data storage
    Decision,            # Diamond — yes/no branch
    Delay,               # Half-rounded rect — wait/delay
    Display,             # Curved rect — display output
    Document,            # Wavy-bottom rect — single document
    InputOutput,         # Parallelogram — I/O operation
    Inspection,          # Circle — inspection/review point
    InternalStorage,     # Rect with corner lines — internal storage
    LoopLimit,           # Truncated rect — loop boundary
    ManualInput,         # Slanted-top rect — manual data entry
    ManualLoop,          # Inverted trapezoid — manual loop
    Merge,               # Inverted triangle — merge point
    MultipleDocuments,   # Stacked wavy rects — multiple documents
    OffPageConnectorLeft,  # Arrow left — continues off-page
    OffPageConnectorRight, # Arrow right — continues off-page
    Or,                  # Circle with cross — OR junction
    PredefinedProcess,   # Rect with side bars — subroutine/predefined
    Preparation,         # Hexagon — setup/initialization
    Sort,                # Hourglass rotated — sort operation
    StartEnd,            # Stadium/pill — terminal (start/end)
    StoredData,          # Curved-side rect — stored data
    SummingJunction,     # Circle with plus — summing junction
)
```

## Example: Decision Flow

```python
from diagrams import Diagram
from diagrams.programming.flowchart import StartEnd, Action, Decision, InputOutput

with Diagram("Order Flow", show=False, direction="TB"):
    start = StartEnd("Start")
    receive = InputOutput("Receive Order")
    validate = Decision("Valid?")
    process = Action("Process Order")
    reject = Action("Reject")
    end = StartEnd("End")

    start >> receive >> validate
    validate >> process >> end
    validate >> reject >> end
```

## Shape Quick Reference

| Shape | Class | Typical Use |
|-------|-------|-------------|
| Pill/Stadium | `StartEnd` | Begin/end of flow |
| Rectangle | `Action` | Process step |
| Diamond | `Decision` | Conditional branch |
| Parallelogram | `InputOutput` | Data input/output |
| Cylinder | `Database` | Data store |
| Wavy rect | `Document` | Document artifact |
| Hexagon | `Preparation` | Setup/init step |
| Rect + sidebars | `PredefinedProcess` | Subroutine call |
| Circle | `Inspection` | Review/check point |
| Inverted triangle | `Merge` | Converge paths |
