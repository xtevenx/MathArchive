#include <climits>
#include <cstddef>

template <typename T>
class SegTree {
    /* Array based segment tree implementation. 
     * T must define the addition (+) and assignment (=) operators.
     * TODO: implement range queries.
     * */

    private:
        // Length of this->data; always a power of two.
        size_t max_size;

        // Array representing the tree.
        // The last max_size/2 holds the actual data, the max_size/4 before
        // them are their parents, max_size/8 their grandparents, etc.
        // Note: because of how the math works out, data[0] is nothing.
        T *data;

    public:
        SegTree(const size_t &n) {
            this->max_size = 1 << (CHAR_BIT * sizeof(size_t) - __builtin_clz(n) + 1);
            this->data = new T[this->max_size];
        }

        ~SegTree() { delete[] this->data; }

        T& operator [](size_t i) const {
            return this->data[i + (this->max_size >> 1)];
        }

        T& root() const {
            return this->data[1];
        }

        void build() {
            for (int i = this->max_size - 2; i >= 2; i -= 2) {
                this->data[i >> 1] = this->data[i] + this->data[i + 1];
            }
        }

        void update(size_t i) {
            for (i = (i + (this->max_size >> 1)) >> 1; i >= 1; i >>= 1) {
                this->data[i] = this->data[i << 1] + this->data[(i << 1) + 1];
            }
        }
};
