// Physical memory allocator, for user processes,
// kernel stacks, page-table pages,
// and pipe buffers. Allocates whole 4096-byte pages.

#include "types.h"
#include "param.h"
#include "memlayout.h"
#include "spinlock.h"
#include "riscv.h"
#include "defs.h"

void freerange(void *pa_start, void *pa_end);

extern char end[]; // first address after kernel.
                   // defined by kernel.ld.

struct run {
  struct run *next;
};

struct {
  struct spinlock lock;
  struct run *freelist;
} kmem;

#define PA2INDEX(pa) ((((uint64)(pa)) - KERNBASE) >> 12)
#define NUM_PAGES (((uint64)PHYSTOP - KERNBASE) >> 12)

static int ref_count[NUM_PAGES];
static struct spinlock ref_lock;

void
kinit()
{
  initlock(&kmem.lock, "kmem");
  initlock(&ref_lock, "ref_lock");
  for (int i = 0; i < (int)NUM_PAGES; i++) {
    ref_count[i] = 1;
  }
  freerange(end, (void *)PHYSTOP);
}

void
freerange(void *pa_start, void *pa_end)
{
  char *p;
  p = (char *)PGROUNDUP((uint64)pa_start);
  for (; p + PGSIZE <= (char *)pa_end; p += PGSIZE)
    kfree(p);
}

void
kref_inc(void *pa)
{
  if (((uint64)pa % PGSIZE) != 0 || (char *)pa < end || (uint64)pa >= PHYSTOP)
    panic("kref_inc");
  acquire(&ref_lock);
  ref_count[PA2INDEX(pa)]++;
  release(&ref_lock);
}

int
kref_get(void *pa)
{
  if (((uint64)pa % PGSIZE) != 0 || (char *)pa < end || (uint64)pa >= PHYSTOP)
    panic("kref_get");
  acquire(&ref_lock);
  int c = ref_count[PA2INDEX(pa)];
  release(&ref_lock);
  return c;
}

// Free the page of physical memory pointed at by pa,
// which normally should have been returned by a
// call to kalloc().  (The exception is when
// initializing the allocator; see kinit above.)
void
kfree(void *pa)
{
  struct run *r;

  if (((uint64)pa % PGSIZE) != 0 || (char *)pa < end || (uint64)pa >= PHYSTOP)
    panic("kfree");

  acquire(&ref_lock);
  if (ref_count[PA2INDEX(pa)] > 1) {
    ref_count[PA2INDEX(pa)]--;
    release(&ref_lock);
    return;
  }
  ref_count[PA2INDEX(pa)] = 0;
  release(&ref_lock);

  // Fill with junk to catch dangling refs.
  memset(pa, 1, PGSIZE);

  r = (struct run *)pa;

  acquire(&kmem.lock);
  r->next = kmem.freelist;
  kmem.freelist = r;
  release(&kmem.lock);
}

// Allocate one 4096-byte page of physical memory.
// Returns a pointer that the kernel can use.
// Returns 0 if the memory cannot be allocated.
void *
kalloc(void)
{
  struct run *r;

  acquire(&kmem.lock);
  r = kmem.freelist;
  if (r)
    kmem.freelist = r->next;
  release(&kmem.lock);

  if (r) {
    memset((char *)r, 5, PGSIZE); // fill with junk
    acquire(&ref_lock);
    ref_count[PA2INDEX(r)] = 1;
    release(&ref_lock);
  }
  return (void *)r;
}
