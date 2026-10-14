# Reference integrity

When a shared symbol, schema, API or configuration contract changes:

1. search its direct consumers before mutation;
2. update only consumers in the approved scope;
3. search old and new references after mutation;
4. explain intentional leftovers;
5. run the smallest check that proves compatibility.

This is a deterministic closure check, not a separate cognitive skill.
