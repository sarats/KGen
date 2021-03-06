module kernel
        
        integer(kind=4), parameter :: real_kind=4
        integer(kind=4), parameter :: np = 2
        public add
       
        contains

        subroutine add(a, b, c)
                real(kind=real_kind), dimension(np,np), intent(in) :: a
                real(kind=real_kind), dimension(np,np), intent(in) :: b
                real(kind=real_kind), dimension(np,np), intent(out) :: c

                c = a + b

        end subroutine add

end module kernel
