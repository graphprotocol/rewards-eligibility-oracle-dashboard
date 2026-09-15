# GDS Patterns

Common UI compositions that demonstrate proper GDS usage. These are **inspiration, not templates** — adapt and combine them for your specific needs. Don't copy them verbatim.

## Dashboard Stats

BAD: Cards for every stat, nested in a container card.

```tsx
<Card>
  <div className="grid grid-cols-4 gap-4">
    <Card>Total: 100</Card>
    <Card>Active: 50</Card>
    <Card>Pending: 30</Card>
    <Card>Failed: 20</Card>
  </div>
</Card>
```

GOOD: Description list.

```tsx
<DescriptionList orientation="horizontal">
  <DescriptionList.Item label="Total" addon={<Status variant="brand" />}>100</DescriptionList.Item>
  <DescriptionList.Item label="Active" addon={<Status variant="success" />}>
    50
  </DescriptionList.Item>
  <DescriptionList.Item label="Pending" addon={<Status variant="warning" />}>
    30
  </DescriptionList.Item>
  <DescriptionList.Item label="Failed" addon={<Status variant="error" />}>
    20
  </DescriptionList.Item>
</DescriptionList>

// OR, for a more custom design:

<dl className="flex gap-6">
  <div>
    <dt className="text-12 text-muted">Total</dt>
    <dd className="mt-1 text-20 font-medium">100</dd>
  </div>
  <Divider orientation="vertical" />
  <div>
    <dt className="text-12 text-muted">Active</dt>
    <dd className="mt-1 text-20 font-medium">50</dd>
  </div>
</dl>
```

## Activity Lists

BAD: Stacked cards for each item.

```tsx
<div className="grid grid-cols-4 gap-4">
  {items.map((item) => (
    <Card key={item.id}>
      <p>{item.title}</p>
      <p>{item.time}</p>
    </Card>
  ))}
</div>
```

GOOD: Table with proper semantic markup.

```tsx
<Table>
  <Table.Header>
    <Table.HeaderCell>Event</Table.HeaderCell>
    <Table.HeaderCell>Time</Table.HeaderCell>
    <Table.HeaderCell>Status</Table.HeaderCell>
  </Table.Header>
  <Table.Body>
    {items.map((item) => (
      <Table.Row key={item.id}>
        <Table.Cell>{item.title}</Table.Cell>
        <Table.Cell className="text-muted">{item.time}</Table.Cell>
        <Table.Cell>
          <Status variant={item.status}>{item.statusLabel}</Status>
        </Table.Cell>
      </Table.Row>
    ))}
  </Table.Body>
</Table>

// OR, for less complex data, a simple list with borders between items:

<ul className="text-14">
  {items.map((item) => (
    <li
      key={item.id}
      className="flex justify-between gap-4 py-3 not-first:border-t not-first:border-subtle"
    >
      <span className="truncate">{item.title}</span>
      <span className="shrink-0 text-muted">{item.time}</span>
    </li>
  ))}
</ul>
```

## Transaction/Record Details

GOOD: Description list, optionally inside a card.

```tsx
<Card variant="tertiary">
  <h3 className="mb-4 text-16 font-medium">Transaction Details</h3>
  <DescriptionList>
    <DescriptionList.Item label="Hash">
      <Address address={tx.hash} />
    </DescriptionList.Item>
    <DescriptionList.Item label="From">
      <Address address={tx.from}>{tx.fromEns}</Address>
    </DescriptionList.Item>
    <DescriptionList.Item label="Value">{tx.value} ETH</DescriptionList.Item>
    <DescriptionList.Item label="Status">
      <Status variant={tx.success ? 'success' : 'error'}>
        {tx.success ? 'Confirmed' : 'Failed'}
      </Status>
    </DescriptionList.Item>
  </DescriptionList>
</Card>
```

## Form Layouts

**Standard form with proper spacing:**

```tsx
<form onSubmit={handleSubmit} className="flex flex-col gap-6">
  <Input
    label="Subgraph Name"
    description="A unique identifier for your subgraph"
    value={name}
    onValueChange={setName}
  />
  <Input label="Description" value={description} onValueChange={setDescription} />
  <TextArea label="Schema" value={schema} onValueChange={setSchema} />
  <ButtonGroup>
    <Button variant="tertiary" onClick={onCancel}>
      Cancel
    </Button>
    <Button variant="secondary" type="submit">
      Create Subgraph
    </Button>
  </ButtonGroup>
</form>
```

Note: Submit is `secondary`, not `primary`. Save the `primary` for the most critical action on the entire page.

## Navigation Sidebars

BAD: Large category labels, small nav items, poor touch targets.

GOOD: Category labels smaller than items, icons, adequate spacing, clear active state. Uses `ButtonOrLink` (from `@graphprotocol/gds-react/base`) instead of raw `<a>` for router integration without visual opinions.

```tsx
<nav className="flex flex-col gap-6 p-4">
  <div>
    <div className="mb-2 px-3 text-10 text-caption text-muted">Overview</div>
    <div className="flex flex-col gap-1">
      <ButtonOrLink
        href="/"
        aria-current
        className="flex items-center gap-2 rounded-8 px-3 py-2 text-14 font-medium text-muted transition-colors hover:bg-muted current:bg-muted current:text-default"
      >
        <HouseIcon alt="" />
        <span className="truncate">Dashboard</span>
      </ButtonOrLink>
      <ButtonOrLink
        href="/analytics"
        className="flex items-center gap-2 rounded-8 px-3 py-2 text-14 font-medium text-muted transition-colors hover:bg-muted current:bg-muted current:text-default"
      >
        <ChartLineUpIcon alt="" />
        <span className="truncate">Analytics</span>
      </ButtonOrLink>
    </div>
  </div>

  <div>
    <div className="mb-2 px-3 text-10 text-caption text-muted">Subgraphs</div>
    <div className="flex flex-col gap-1">
      <ButtonOrLink
        href="/my-subgraphs"
        className="flex items-center gap-2 rounded-8 px-3 py-2 text-14 font-medium text-muted transition-colors hover:bg-muted current:bg-muted current:text-default"
      >
        <SubgraphIcon alt="" />
        <span className="truncate">My Subgraphs</span>
      </ButtonOrLink>
      <ButtonOrLink
        href="/deployments"
        className="flex items-center gap-2 rounded-8 px-3 py-2 text-14 font-medium text-muted transition-colors hover:bg-muted current:bg-muted current:text-default"
      >
        <RocketIcon alt="" />
        <span className="truncate">Deployments</span>
      </ButtonOrLink>
    </div>
  </div>
</nav>
```

## Action Menus

**Use Menu for dropdowns:**

```tsx
<Menu
  trigger={
    <Button variant="tertiary" addonAfter={CaretDownInteractiveIcon}>
      Actions
    </Button>
  }
>
  <Menu.Item>Edit</Menu.Item>
  <Menu.Item>Duplicate</Menu.Item>
  <Menu.Item variant="danger">Delete</Menu.Item>
</Menu>
```

## Wallet Connection

```tsx
{
  isConnected ? (
    <Menu trigger={<Address variant="enclosed" address={account} copy={false} />}>
      <Menu.Item>Copy Address</Menu.Item>
      <Menu.Item>Disconnect</Menu.Item>
    </Menu>
  ) : (
    <Button variant="secondary" onClick={connect}>
      Connect Wallet
    </Button>
  )
}
```

Note: Connect is `secondary`, not `primary`. The primary action is whatever the user came to do (delegate, stake, etc.), not connecting their wallet.

## Empty States

```tsx
<div className="flex flex-col items-center justify-center py-16 text-center">
  <TrayIcon alt="" size={8} className="text-muted" />
  <h3 className="mt-4 text-16 font-medium">No subgraphs yet</h3>
  <p className="mt-2 max-w-sm text-14 text-muted">
    Create your first subgraph to start indexing blockchain data.
  </p>
  <Button variant="secondary" className="mt-6">
    Create Subgraph
  </Button>
</div>
```

## Responsive UIs

**Use `Pane` for responsive sidebars.** On desktop it's a docked sidebar; on mobile it overlays.

```tsx
<div className="flex min-h-full w-full flex-col border border-default">
  <header className="border-b border-default bg-subtle p-4">
    <Pane.ToggleButton name="sidebar">
      <SidebarLeftInteractiveIcon />
    </Pane.ToggleButton>
  </header>
  <Pane.Container className="flex-1">
    <Pane
      name="sidebar"
      className="w-64 border-e border-default bg-subtle p-6 max-sm:prop-layout-overlay"
    >
      Sidebar content
    </Pane>
    <main className="p-6">Main content</main>
  </Pane.Container>
</div>
```

**Hide/show labels on mobile:**

```tsx
<Button addonBefore={PlusIcon} className="max-sm:prop-hide-label-true">
  Create Subgraph
</Button>
```

**Responsive grids:**

```tsx
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
  {items.map((item) => (
    <Card key={item.id}>{/* ... */}</Card>
  ))}
</div>
```

## Clickable Cards

**Card as a link or button with interactive content inside.** Use the `interactiveContent` prop to prevent rendering a button/link inside another button/link.

```tsx
<Card
  interactiveContent
  // If the card is a link:
  href="/agents/1"
  // If the card is a button:
  onClick={() => {
    /* ... */
  }}
>
  <div className="flex justify-between gap-4">
    <div>
      <h3 className="font-medium">My Agent</h3>
      <p className="mt-1 text-14 text-muted">An agent that does things</p>
    </div>
    <ButtonGroup variant="tertiary">
      <Button>
        <PencilIcon alt="Edit" />
      </Button>
      <Button>
        <TrashIcon alt="Delete" />
      </Button>
    </ButtonGroup>
  </div>
</Card>
```

## Checkable Cards

**Use `.Area` components to make entire cards checkable.** `Checkbox.Area`, `Radio.Area`, and `Switch.Area` wrap a `Card` rendered as a `<label>` — clicking anywhere on the card toggles the control.

```tsx
// Toggle (on/off)
<Switch.Area render={<Card as="label" />}>
  <Switch checked={enabled} onCheckedChange={setEnabled}>
    <span className="block">Email notifications</span>
    <span className="mt-1 block text-12 text-muted">Receive updates via email</span>
  </Switch>
</Switch.Area>

// Single-select (pick one)
<Radio.Group name="theme">
  <div className="flex flex-col gap-3">
    <Radio.Area render={<Card as="label" />}>
      <Radio value="dark">Dark mode</Radio>
    </Radio.Area>
    <Radio.Area render={<Card as="label" />}>
      <Radio value="light">Light mode</Radio>
    </Radio.Area>
  </div>
</Radio.Group>

// Multi-select (pick many)
<div className="flex flex-col gap-3">
  <Checkbox.Area render={<Card as="label" />}>
    <Checkbox checked={a} onCheckedChange={setA}>
      Option A
    </Checkbox>
  </Checkbox.Area>
  <Checkbox.Area render={<Card as="label" />}>
    <Checkbox checked={b} onCheckedChange={setB}>
      Option B
    </Checkbox>
  </Checkbox.Area>
</div>
```

## Collapsibles / Accordion

**Use native `<details>`/`<summary>` — not `useState`-based toggles.** Put padding on `<summary>`, not `<details>`, so the clickable area matches the visual target. Use a container with flex + gap for spacing between items.

BAD: Padding on `<details>`, no open indicator.

```tsx
<div className="flex flex-col">
  {faqs.map((faq) => (
    <details key={faq.question} className="border-b border-muted py-4">
      <summary>{faq.question}</summary>
      <p>{faq.answer}</p>
    </details>
  ))}
</div>
```

GOOD: No padding on `<details>`, open indicator, hover highlight.

```tsx
<div className="flex flex-col gap-1">
  {faqs.map((faq) => (
    <details key={faq.question} className="group">
      <summary className="flex items-center justify-between gap-4 rounded-8 px-4 py-3 text-16 font-medium hover:bg-muted">
        {faq.question}
        <CaretDownInteractiveIcon alt="" />
      </summary>
      <div className="px-4 pb-3 text-14 text-muted">{faq.answer}</div>
    </details>
  ))}
</div>
```

GOOD: Same as above but with a bordered/divided style.

```tsx
<div className="flex flex-col">
  {faqs.map((faq) => (
    <details key={faq.question} className="group not-first:border-t not-first:border-subtle">
      <summary className="flex items-center justify-between gap-4 py-4 text-16 font-medium">
        {faq.question}
        <CaretDownInteractiveIcon alt="" />
      </summary>
      <div className="pb-4 text-14 text-muted">{faq.answer}</div>
    </details>
  ))}
</div>
```

**Animated version** using `ExperimentalTransition` for smooth height transitions:

```tsx
function Disclosure({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)

  return (
    <details
      open={detailsOpen || undefined}
      onToggle={(event) => {
        // Handle the browser's "find" feature opening the disclosure
        if (event.newState === 'open') {
          setOpen(true)
          setDetailsOpen(true)
        }
      }}
    >
      <summary
        onClick={(event) => {
          event.preventDefault()
          const newOpen = !open
          setOpen(newOpen)
          if (newOpen) setDetailsOpen(true)
        }}
        className="flex items-center justify-between gap-4 py-4 text-16 font-medium"
      >
        {trigger}
        <CaretDownInteractiveIcon alt="" className="text-muted" />
      </summary>
      <ExperimentalTransition
        visibleKey={open ? 'content' : null}
        onTransitionEnd={({ exited }) => {
          if (exited.has('content')) setDetailsOpen(false)
        }}
        renderChild={(renderProps) => (
          /**
           * `hidden` prevents the browser's "find" feature from finding the disclosure's content
           * when it is closed, so we make it invisible without removing it from the accessibility
           * tree instead (with `pointer-events-none absolute opacity-0`).
           *
           * TODO: Replace with `hidden={state.status === 'hidden' ? 'until-found' : false}` once
           * it's supported by React: https://github.com/facebook/react/issues/24740.
           */
          <span
            {...renderProps}
            hidden={false}
            className={cn(
              renderProps.className,
              'data-[status=hidden]:pointer-events-none data-[status=hidden]:absolute data-[status=hidden]:opacity-0',
            )}
          />
        )}
      >
        <div key="content" className="pb-4 text-14 text-muted">
          {children}
        </div>
      </ExperimentalTransition>
    </details>
  )
}
```

## Multi-step Modals

For a `Modal` that walks a user through several steps (confirm → sign → success, etc.), declare the possible steps up front and drive `currentStep` from state. The function-form `children` receives `{ currentStep, setCurrentStep, closeModal }` — switch on `currentStep` and return the JSX for that step. **Always render the exact same set of `<Modal.Header>` / `<Modal.Body>` / `<Modal.Footer>` in every step** — leave one empty if a step doesn't need it, don't omit it — otherwise the step transition breaks.

```tsx
type Step = 'confirm' | 'sign' | 'success'

function DeleteSubgraphModal() {
  const [currentStep, setCurrentStep] = useState<Step>('confirm')

  return (
    <Modal
      trigger={<Button variant="danger">Delete</Button>}
      steps={['confirm', 'sign', 'success']}
      currentStep={currentStep}
      onCurrentStepChange={setCurrentStep}
    >
      {({ currentStep, setCurrentStep, closeModal }) => {
        switch (currentStep) {
          case 'confirm':
            return (
              <>
                <Modal.Header title="Delete Subgraph" />
                <Modal.Body>Are you sure? This is irreversible.</Modal.Body>
                <Modal.Footer
                  actionPrimary={
                    <Button variant="danger" onClick={() => setCurrentStep('sign')}>
                      Delete
                    </Button>
                  }
                  actionSecondary={<Button onClick={closeModal}>Cancel</Button>}
                />
              </>
            )
          case 'sign':
            return (
              <>
                <Modal.Header title="Signature Required" />
                <Modal.Body>Please confirm on your wallet.</Modal.Body>
                <Modal.Footer />
              </>
            )
          case 'success':
            return (
              <>
                <Modal.Header title="Deleted" />
                <Modal.Body>Your subgraph has been deleted.</Modal.Body>
                <Modal.Footer actionPrimary={<Button onClick={closeModal}>Close</Button>} />
              </>
            )
        }
      }}
    </Modal>
  )
}
```

**Extracting steps into their own components?** Wrap the conditional in an outer `<Modal.Step>` (provider), and have each extracted step component wrap its `<Modal.Header>` / `<Modal.Body>` / `<Modal.Footer>` in an inner `<Modal.Step>` (consumer). Together they preserve stable element identity for the Header/Body/Footer slots across steps, so React doesn't remount them and the transition still animates.

```tsx
<Modal.Step>
  {currentStep === 'confirm' ? (
    <ConfirmStep onNext={() => setCurrentStep('sign')} onCancel={closeModal} />
  ) : currentStep === 'sign' ? (
    <SignStep />
  ) : (
    <SuccessStep onClose={closeModal} />
  )}
</Modal.Step>
```

Each extracted step wraps its slots in `<Modal.Step>`:

```tsx
function ConfirmStep({ onNext, onCancel }: { onNext: () => void; onCancel: () => void }) {
  return (
    <Modal.Step>
      <Modal.Header title="Delete Subgraph" />
      <Modal.Body>Are you sure? This is irreversible.</Modal.Body>
      <Modal.Footer
        actionPrimary={
          <Button variant="danger" onClick={onNext}>
            Delete
          </Button>
        }
        actionSecondary={<Button onClick={onCancel}>Cancel</Button>}
      />
    </Modal.Step>
  )
}
```

Without the `<Modal.Step>` provider/consumer pair, React would treat each conditional branch as a different component (`ConfirmStep` vs `SignStep` vs `SuccessStep`) and remount everything inside — including the Header/Body/Footer — on every step change, which breaks the transition.
