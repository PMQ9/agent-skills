# Architecture Detection Guide

Language-agnostic detection cues and worked before/after examples for the eight
categories the architecture reviewer hunts. Examples use pseudo-code that reads
like Python/JS/TS; translate the pattern to whatever the diff is written in — the
shape of the problem is the same across languages, frameworks, and stacks.

Every fix here is a design change: a responsibility moves, a dependency flips, a
seam appears, or a boundary tightens. **None of it is about making code faster.**
If your only note is "this could be more efficient," it does not belong in an
architecture review — drop it.

## Table of contents

1. Separation of concerns
2. Layering
3. Responsibilities
4. Coupling
5. Abstraction boundaries
6. API / contract design
7. Code organization
8. Maintainability & change cost

---

## 1. Separation of concerns

**Tell:** a function or class you can't describe without "and" — it parses input
*and* applies a business rule *and* writes to storage *and* formats a response.
Mixed levels of abstraction in one body; validation, computation, and I/O
interleaved.

**Cost:** every one of those jobs now has to change together. You can't unit-test
the rule without a database and an HTTP request; you can't reuse it from a job or
CLI; a change to the wire format risks the business logic.

```
# before — one handler does everything
def create_order(request):
    body = json.loads(request.body)              # parsing
    if body["qty"] <= 0:                          # validation
        return HttpResponse(status=400)
    total = body["qty"] * price_for(body["sku"])  # business rule
    db.execute("INSERT INTO orders ...", ...)     # persistence
    return HttpResponse(json.dumps({"total": total}))  # formatting

# after — each concern has a home
def create_order(request):                        # web layer: shape in/out only
    dto = parse_order_request(request)
    order = order_service.place_order(dto)        # rule + persistence live inward
    return json_response(order)
```

The fix is almost never "add a comment" — it's "split the concerns so each can
change and be tested on its own."

## 2. Layering

**Tell:** dependencies pointing the wrong way. Domain/business code importing web,
ORM, or framework types; a repository or model calling up into a controller;
business logic reading `request.headers` or building an `HttpResponse`; a view/UI
talking straight to the database. Look at the *imports* the diff adds — they
reveal the direction of the arrow.

**Cost:** the inner layer can no longer be used or tested without the outer one.
The domain becomes married to a framework you may want to swap; a controller
change can break a model.

```
# before — domain reaches up into the web layer
# file: domain/pricing.py
from web.responses import HttpResponse            # 🚩 wrong-way import
def price(cart):
    if not cart.items:
        return HttpResponse(status=400)           # domain shouldn't know HTTP
    ...

# after — domain returns a plain result; the web layer maps it
# file: domain/pricing.py
def price(cart):
    if not cart.items:
        raise EmptyCartError()
    return total
# file: web/checkout.py
try:    return json_response(price(cart))
except EmptyCartError: return HttpResponse(status=400)
```

Name the layers in your finding ("domain → web") so the direction is unambiguous.

## 3. Responsibilities

**Tell:** logic living in the wrong place. Business rules embedded in a
controller, template, or migration; a `Manager`/`Helper`/`Utils` class that has
accreted unrelated methods (god object); an entity that's pure getters/setters
with all its behavior implemented elsewhere (anemic domain model); the same rule
duplicated in two handlers.

**Cost:** rules that belong together are scattered, so a change means hunting
through unrelated files and hoping you found every copy. Ownership is unclear, so
bugs reappear.

```
# before — anemic model, rule lives in the caller
class Account:  # just data
    balance: int
def withdraw(account, amount):          # rule floats free, easy to duplicate
    if amount > account.balance: raise ...
    account.balance -= amount

# after — behavior lives with the data it guards
class Account:
    def withdraw(self, amount):
        if amount > self.balance: raise InsufficientFunds()
        self.balance -= amount
```

Point at *where the logic should live* and why that's its natural home.

## 4. Coupling

**Tell:** modules that know too much about each other. Reaching into another
object's internals (`a.b.c.do()`); depending on a concrete class where the
behavior is all that matters; hidden coupling through shared global/mutable state
or a singleton; a change in one module forcing edits in several unrelated ones;
import cycles (A imports B imports A).

**Cost:** you can't change or test one module in isolation — it drags its
neighbors along. Circular deps make the build/order fragile and the code
impossible to reason about piece by piece.

```
# before — depends on a concrete sender + reaches through it
class SignupService:
    def __init__(self):
        self.mailer = SmtpMailer("smtp.internal", 25)   # concrete, hard-wired
    def register(self, u):
        self.mailer.connection.socket.send(...)         # reaching into internals

# after — depend on a small interface, injected
class SignupService:
    def __init__(self, notifier: Notifier):             # depend on behavior
        self.notifier = notifier
    def register(self, u):
        self.notifier.welcome(u)                        # ask, don't reach in
```

Distinguish *necessary* coupling (a service legitimately uses its repository)
from *accidental* coupling (it reaches through the repository into the DB
driver). Only the accidental kind is a finding.

## 5. Abstraction boundaries

**Tell:** the abstraction leaks. ORM/SQL types, framework request objects, or
raw dicts crossing a "clean" interface; a repository whose method returns a live
query object instead of domain data; a wrapper class that just forwards calls and
adds nothing; or the opposite — a missing seam where a boundary obviously belongs
(a third-party API called inline in ten places).

**Cost:** a leaky boundary means callers depend on the *implementation*, so you
can't change what's behind it — the whole point of the seam is gone. A pointless
wrapper adds indirection with no payoff. A missing seam means a vendor swap
touches the whole codebase.

```
# before — repository leaks the ORM; callers now depend on the ORM
class UserRepo:
    def find_active(self):
        return User.objects.filter(active=True)   # returns a live QuerySet 🚩

# after — the boundary returns domain data, hides the mechanism
class UserRepo:
    def find_active(self) -> list[User]:
        return list(User.objects.filter(active=True))
```

Ask: "if I replaced what's behind this interface, would callers have to change?"
If yes, the boundary leaks.

## 6. API / contract design

**Tell:** the shape a module exposes to its callers is confusing or fragile.
Boolean/flag parameters that select between two behaviors (`render(pdf=True)`
should be two methods); internal types leaked in a public signature; inconsistent
naming across sibling methods; a poor error contract (swallowing exceptions,
returning `null` in some paths and raising in others); one call that does three
unrelated things, or three calls where one cohesive operation belongs; a breaking
change to an already-published interface.

**Cost:** callers have to memorize quirks, guess at error handling, and get
broken by changes. This is about the *contract's shape*, not HTTP status codes or
pagination tuning — keep it at the design level.

```
# before — flag param + inconsistent error contract
def get_user(id, throw=False):
    u = db.find(id)
    if not u and throw: raise NotFound()
    return u              # sometimes None, sometimes raises — caller can't tell

# after — one clear contract per method
def get_user(id) -> User | None: ...      # explicit optional
def require_user(id) -> User: ...         # always raises if missing
```

## 7. Code organization

**Tell:** where things live works against you. Unrelated responsibilities lumped
into one giant file/module; one feature's code smeared across many packages;
package structure organized by technical type (`controllers/`, `models/`) in a
way that hides the domain when feature-cohesion would serve better (or the
reverse); names that mislead about what a unit does; the diff moves or copies
code without giving it a sensible home.

**Cost:** people can't find things, and "where does this go?" has no obvious
answer — so new code lands wherever, and the structure decays further.

```
# before — a 1,200-line utils.py that everything imports
utils.py  # date math + auth + currency + CSV export + retry logic

# after — cohesive modules with honest names
dates.py  auth.py  money.py  export/csv.py  retry.py
```

This category is often Minor/Nit — but a structure that actively hides the domain
or forces wrong-way imports can be Major. Judge by change cost, not tidiness.

## 8. Maintainability & change cost

**Tell:** the summary lens. Would the next person find, understand, and safely
change this? Watch both directions:

- **Under-design:** no seam to test the logic; a single 300-line method; implicit
  state that must be set up in the right order; behavior that only its author
  could safely extend.
- **Over-design:** an interface with one implementation and no prospect of a
  second; a factory/strategy/abstract-base scaffold for a problem that has one
  case; layers of indirection that a reader must peel to find five lines of real
  work. Premature abstraction is a real finding — flag it as readily as
  under-design.

**Cost:** either extreme raises the cost of the *next* change — under-design
because it's fragile, over-design because you must understand a cathedral to
touch a closet.

```
# before — over-engineered for a single, stable case
class DiscountStrategyFactory:
    def create(self, kind): return {"flat": FlatDiscount()}[kind]   # only "flat" exists

# after — until there's a second case, just do the thing
def apply_discount(total): return total * 0.9
```

The honest question is "does this complexity earn its keep *today*?" If a simpler
structure would serve the change in front of you, say so — adding abstraction is
not automatically an improvement.

---

## Calibration notes

- **Not every difference is a finding.** "I'd have done it differently" is not a
  design flaw. Tie every finding to concrete change cost.
- **Respect scope.** A PR is not a redesign. If the only real fix is a large
  refactor out of scope for this change, note the structural risk briefly and
  say it's a follow-up — don't block a working change on a rewrite unless the
  design actively endangers the codebase.
- **Stay out of the performance lane.** No loop hoisting, no query narrowing, no
  allocation counting. If it's a micro-optimization, it is not this review's job.
